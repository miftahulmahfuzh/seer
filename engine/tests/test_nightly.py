import argparse
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, db, dividends, universe
from seer_engine.commands import nightly
from seer_engine.dividends import Dividend
from seer_engine.massive import MassiveError
from seer_engine.splits import Split

UTC = timezone.utc
FRI_NIGHT = datetime(2026, 10, 2, 23, 0, tzinfo=UTC)
D0 = date(2026, 9, 29)
D_WED = date(2026, 9, 30)
D_THU = date(2026, 10, 1)
D_FRI = date(2026, 10, 2)
MON_AFTER = date(2026, 10, 5)

UNIVERSE = ["SPY", "AAPL", "MSFT", "NVDA", "BRK.B", "AMZN", "GOOGL", "META", "TSLA", "AVGO"]
FX = (D_FRI, Decimal("17950.0000"))


def fx_ok():
    return FX


class FakeMassive:
    """grouped_data: {date: {symbol: (o, h, l, c, v)}}; splits_data: {date: [Split]};
    dividends_data: {date: [Dividend]} (one per Massive row, not summed); dividends_fail raises
    from dividends() only."""

    def __init__(self, grouped_data=None, splits_data=None, fail=None, dividends_data=None, dividends_fail=None):
        self.grouped_data = grouped_data or {}
        self.splits_data = splits_data or {}
        self.dividends_data = dividends_data or {}
        self.fail = fail
        self.dividends_fail = dividends_fail
        self.calls = []

    def grouped(self, d):
        self.calls.append(("grouped", d))
        if self.fail is not None:
            raise self.fail
        rows = self.grouped_data.get(d)
        if not rows:
            raise MassiveError(f"grouped daily {d}: no results (not published yet?)")
        return {s: bars.make_bar(s, d, *v) for s, v in rows.items()}

    def splits(self, d):
        self.calls.append(("splits", d))
        return list(self.splits_data.get(d, []))

    def dividends(self, d):
        self.calls.append(("dividends", d))
        if self.dividends_fail is not None:
            raise self.dividends_fail
        return list(self.dividends_data.get(d, []))


def day(symbols=UNIVERSE, price=100.0, extra=()):
    rows = {s: (price, price + 1, price - 1, price + 0.5, 1_000_000.4) for s in symbols}
    rows["ZZZZ"] = (5.0, 5.0, 5.0, 5.0, 10.0)  # non-universe ticker: must not be stored
    for s, v in extra:
        rows[s] = v
    return rows


@pytest.fixture
def fixed_universe(monkeypatch):
    members = set(UNIVERSE)
    monkeypatch.setattr(universe, "symbols_for_bars", lambda conn, d, grace_days=30: set(members))
    return members


def seed(conn, *days, symbols=UNIVERSE):
    with db.transaction(conn, False):
        bars.upsert_bars(conn, [bars.make_bar(s, d, 99, 101, 98, 100, 1000) for d in days for s in symbols])


def q(conn, sql, params=()):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    conn.rollback()
    return rows


def real_runs(conn):
    return q(conn, "SELECT id, status, data_date, session_date, error FROM runs WHERE NOT is_demo ORDER BY id")


def bars_on(conn, d):
    return q(conn, "SELECT symbol FROM bars WHERE date = %s ORDER BY symbol", (d,))


CHECKSUM_TABLES = {
    "bars": "x.symbol, x.date",
    "dividends": "x.symbol, x.ex_date",
    "fx_rates": "x.date",
    "runs": "x.id",
    "split_adjustments": "x.symbol, x.execution_date",
}


def checksums(conn):
    out = {}
    for table, order in CHECKSUM_TABLES.items():
        out[table] = q(
            conn,
            f"SELECT count(*), coalesce(md5(string_agg(x::text, '|' ORDER BY {order})), '') FROM {table} x",
        )[0]
    return out


def go(conn, client, now=FRI_NIGHT, dry_run=False):
    return nightly.execute(conn, now=now, client=client, dry_run=dry_run, fetch_fx=fx_ok, secret="sekret")


def test_friday_run_writes_bars_fx_and_success_run(pg, fixed_universe):
    seed(pg, D_THU)
    fake = FakeMassive({D_FRI: day()})
    assert go(pg, fake) == 0
    [(run_id, status, data_date, session_date, error)] = real_runs(pg)
    assert (status, data_date, session_date, error) == ("success", D_FRI, MON_AFTER, None)
    assert sorted(r[0] for r in bars_on(pg, D_FRI)) == sorted(UNIVERSE)  # ZZZZ not stored
    assert q(pg, "SELECT date, usd_idr FROM fx_rates") == [FX]
    assert fake.calls == [("grouped", D_FRI), ("splits", D_FRI), ("dividends", D_FRI)]


def test_same_now_twice_leaves_identical_tables(pg, fixed_universe):
    seed(pg, D_THU)
    assert go(pg, FakeMassive({D_FRI: day()})) == 0
    before = checksums(pg)
    second = FakeMassive({D_FRI: day(price=200.0)})
    assert go(pg, second) == 0
    assert checksums(pg) == before
    assert second.calls == []


def test_massive_failure_marks_run_failed_and_writes_no_bars_then_rerun_reuses_row(pg, fixed_universe):
    seed(pg, D_THU)
    assert go(pg, FakeMassive(fail=RuntimeError("boom apiKey=sekret"))) == 1
    [(run_id, status, _, session_date, error)] = real_runs(pg)
    assert status == "failed" and session_date == MON_AFTER
    assert "boom" in error and "sekret" not in error
    assert bars_on(pg, D_FRI) == []
    assert q(pg, "SELECT count(*) FROM fx_rates") == [(0,)]

    assert go(pg, FakeMassive({D_FRI: day()})) == 0
    [(run_id2, status2, _, _, _)] = real_runs(pg)
    assert (run_id2, status2) == (run_id, "success")
    assert len(bars_on(pg, D_FRI)) == len(UNIVERSE)


def test_empty_grouped_marks_run_failed(pg, fixed_universe):
    seed(pg, D_THU)
    assert go(pg, FakeMassive({})) == 1
    assert real_runs(pg)[0][1] == "failed"
    assert "no results" in real_runs(pg)[0][4]
    assert bars_on(pg, D_FRI) == []


def test_fx_failure_marks_run_failed_and_writes_no_bars(pg, fixed_universe):
    seed(pg, D_THU)

    def fx_down():
        raise RuntimeError("frankfurter down")

    rc = nightly.execute(pg, now=FRI_NIGHT, client=FakeMassive({D_FRI: day()}), fetch_fx=fx_down)
    assert rc == 1
    assert real_runs(pg)[0][1] == "failed"
    assert bars_on(pg, D_FRI) == []


def test_gap_of_three_sessions_fetched_in_order(pg, fixed_universe):
    seed(pg, D0)
    fake = FakeMassive({D_WED: day(), D_THU: day(), D_FRI: day()})
    assert go(pg, fake) == 0
    assert [c for c in fake.calls if c[0] == "grouped"] == [("grouped", D_WED), ("grouped", D_THU), ("grouped", D_FRI)]
    for d in (D_WED, D_THU, D_FRI):
        assert len(bars_on(pg, d)) == len(UNIVERSE)


def test_gap_over_thirty_sessions_fails_without_fetching(pg, fixed_universe):
    seed(pg, date(2026, 8, 3))
    fake = FakeMassive({D_FRI: day()})
    assert go(pg, fake) == 1
    assert "gap" in real_runs(pg)[0][4]
    assert fake.calls == []


def test_no_spy_bars_fails(pg, fixed_universe):
    assert go(pg, FakeMassive({D_FRI: day()})) == 1
    assert "backfill" in real_runs(pg)[0][4]


def test_spy_missing_from_grouped_fails(pg, fixed_universe):
    seed(pg, D_THU)
    rows = day()
    del rows["SPY"]
    assert go(pg, FakeMassive({D_FRI: rows})) == 1
    assert "SPY missing" in real_runs(pg)[0][4]
    assert bars_on(pg, D_FRI) == []


def test_coverage_below_90_percent_fails(pg, fixed_universe):
    seed(pg, D_THU)
    rows = day([s for s in UNIVERSE if s not in ("TSLA", "AVGO")])  # 8/10
    assert go(pg, FakeMassive({D_FRI: rows})) == 1
    assert "covers 8/10" in real_runs(pg)[0][4]
    assert bars_on(pg, D_FRI) == []


def test_one_absent_symbol_is_a_warning_not_a_failure(pg, fixed_universe, caplog):
    seed(pg, D_THU)
    rows = day([s for s in UNIVERSE if s != "AVGO"])  # 9/10 = 90%
    caplog.set_level(logging.WARNING)
    assert go(pg, FakeMassive({D_FRI: rows})) == 0
    assert "AVGO" in caplog.text
    assert len(bars_on(pg, D_FRI)) == len(UNIVERSE) - 1


def test_empty_universe_fails(pg, monkeypatch):
    monkeypatch.setattr(universe, "symbols_for_bars", lambda conn, d, grace_days=30: {"SPY"})
    seed(pg, D_THU, symbols=["SPY"])
    assert go(pg, FakeMassive({D_FRI: day()})) == 1
    assert "universe refresh" in real_runs(pg)[0][4]


def test_dry_run_writes_nothing(pg, fixed_universe):
    seed(pg, D_THU)
    before = checksums(pg)
    fake = FakeMassive(
        {D_FRI: day()},
        {D_FRI: [Split("NVDA", D_FRI, Decimal(1), Decimal(10))]},
        dividends_data={D_FRI: [Dividend("SPY", D_FRI, Decimal("1.888834"))]},
    )
    assert go(pg, fake, dry_run=True) == 0
    assert checksums(pg) == before
    assert real_runs(pg) == []
    assert fake.calls == [("grouped", D_FRI), ("splits", D_FRI), ("dividends", D_FRI)]


def test_dry_run_failure_writes_nothing(pg, fixed_universe):
    seed(pg, D_THU)
    before = checksums(pg)
    assert go(pg, FakeMassive(fail=RuntimeError("boom")), dry_run=True) == 1
    assert checksums(pg) == before


def test_split_applied_to_history_once(pg, fixed_universe):
    seed(pg, D_THU, symbols=[s for s in UNIVERSE if s != "NVDA"])
    with db.transaction(pg, False):
        bars.upsert_bars(pg, [bars.make_bar("NVDA", D_THU, 1190, 1210, 1180, 1200, 1_000_000)])
    split = Split("NVDA", D_FRI, Decimal(1), Decimal(10))
    fake = FakeMassive({D_FRI: day(extra=[("NVDA", (121.0, 123.0, 119.0, 122.0, 9_000_000.0))])}, {D_FRI: [split]})
    assert go(pg, fake) == 0
    assert q(pg, "SELECT close, volume FROM bars WHERE symbol='NVDA' AND date=%s", (D_THU,)) == [(Decimal("120.0000"), 10_000_000)]
    assert q(pg, "SELECT close FROM bars WHERE symbol='NVDA' AND date=%s", (D_FRI,)) == [(Decimal("122.0000"),)]
    assert q(pg, "SELECT symbol, applied FROM split_adjustments") == [("NVDA", True)]
    before = checksums(pg)
    assert go(pg, fake) == 0  # same session again: no-op, split not re-applied
    assert checksums(pg) == before


def test_split_inside_multi_session_gap_does_not_touch_fetched_bars(pg, fixed_universe):
    others = [s for s in UNIVERSE if s != "NVDA"]
    seed(pg, D0, symbols=others)
    with db.transaction(pg, False):
        bars.upsert_bars(pg, [bars.make_bar("NVDA", D0, 1200, 1200, 1200, 1200, 1000)])
    # Massive adjusted=true is adjusted as of fetch time: Wed's NVDA bar is already post-split.
    nvda = ("NVDA", (120.0, 121.0, 119.0, 120.5, 10_000.0))
    fake = FakeMassive(
        {D_WED: day(extra=[nvda]), D_THU: day(extra=[nvda]), D_FRI: day(extra=[nvda])},
        {D_THU: [Split("NVDA", D_THU, Decimal(1), Decimal(10))]},
    )
    assert go(pg, fake) == 0
    assert q(pg, "SELECT close FROM bars WHERE symbol='NVDA' AND date=%s", (D0,)) == [(Decimal("120.0000"),)]
    assert q(pg, "SELECT close FROM bars WHERE symbol='NVDA' AND date=%s", (D_WED,)) == [(Decimal("120.5000"),)]


def test_untracked_split_is_ignored(pg, fixed_universe):
    seed(pg, D_THU)
    fake = FakeMassive({D_FRI: day()}, {D_FRI: [Split("ZZZZ", D_FRI, Decimal(1), Decimal(2))]})
    assert go(pg, fake) == 0
    assert q(pg, "SELECT count(*) FROM split_adjustments") == [(0,)]


def test_labor_day_monday_run_is_a_noop_after_friday(pg, fixed_universe):
    fri = date(2026, 9, 4)
    seed(pg, date(2026, 9, 3))
    fake = FakeMassive({fri: day()})
    assert go(pg, fake, now=datetime(2026, 9, 4, 23, 0, tzinfo=UTC)) == 0
    [(_, status, data_date, session_date, _)] = real_runs(pg)
    assert (status, data_date, session_date) == ("success", fri, date(2026, 9, 8))
    before = checksums(pg)
    calls = list(fake.calls)
    assert go(pg, fake, now=datetime(2026, 9, 7, 23, 0, tzinfo=UTC)) == 0
    assert checksums(pg) == before
    assert fake.calls == calls


def test_bars_already_current_still_records_fx_and_finishes(pg, fixed_universe):
    seed(pg, D_FRI)  # e.g. a backfill already reached data_date
    fake = FakeMassive({})
    assert go(pg, fake) == 0
    assert fake.calls == []
    assert real_runs(pg)[0][1] == "success"
    assert q(pg, "SELECT date FROM fx_rates") == [(D_FRI,)]


# ---- dividends and paper-held symbols ----

def stored_dividends(conn):
    return q(conn, "SELECT symbol, ex_date, amount FROM dividends ORDER BY symbol, ex_date")


def hold(conn, symbol, *, strategy="T1", target_session=None):
    """Paper state holding `symbol`: a book position, or a book target for `target_session`."""
    with db.transaction(conn, False):
        conn.execute(
            "INSERT INTO strategies (id, name, sub, icon) VALUES (%s, %s, '', 'sigma') ON CONFLICT (id) DO NOTHING",
            (strategy, strategy),
        )
        if target_session is None:
            conn.execute(
                "INSERT INTO book_positions (strategy_id, symbol, shares, mark, entry_date, entry_price, "
                "days_held, cost_usd, income_usd) VALUES (%s, %s, 10, 50, %s, 50, 1, 0, 0)",
                (strategy, symbol, D_THU),
            )
        else:
            conn.execute(
                "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price) "
                "VALUES (%s, %s, 1, %s, 1, 50)",
                (strategy, target_session, symbol),
            )


GONE_BAR = ("GONE", (50.0, 51.0, 49.0, 50.5, 1000.0))


def test_dividends_for_tracked_symbols_are_summed_and_written_with_the_bars(pg, fixed_universe):
    seed(pg, D_THU)
    fake = FakeMassive(
        {D_FRI: day()},
        dividends_data={
            D_FRI: [
                Dividend("SPY", D_FRI, Decimal("1.888834")),
                Dividend("AAPL", D_FRI, Decimal("0.26")),
                Dividend("AAPL", D_FRI, Decimal("0.01")),  # an SC row on the same ex-date
                Dividend("ZZZZ", D_FRI, Decimal("0.5")),  # not tracked: dropped
            ]
        },
    )
    assert go(pg, fake) == 0
    assert stored_dividends(pg) == [("AAPL", D_FRI, Decimal("0.270000")), ("SPY", D_FRI, Decimal("1.888834"))]
    assert real_runs(pg)[0][1] == "success"
    before = checksums(pg)
    assert go(pg, fake) == 0  # same session again: no-op
    assert checksums(pg) == before


def test_dividends_fetched_for_every_session_of_a_gap(pg, fixed_universe):
    seed(pg, D0)
    fake = FakeMassive(
        {D_WED: day(), D_THU: day(), D_FRI: day()},
        dividends_data={D_THU: [Dividend("MSFT", D_THU, Decimal("0.83"))]},
    )
    assert go(pg, fake) == 0
    assert [c for c in fake.calls if c[0] == "dividends"] == [("dividends", D_WED), ("dividends", D_THU), ("dividends", D_FRI)]
    assert stored_dividends(pg) == [("MSFT", D_THU, Decimal("0.830000"))]


def test_dividend_inside_gap_before_a_split_is_stored_in_post_split_units(pg, fixed_universe):
    others = [s for s in UNIVERSE if s != "NVDA"]
    seed(pg, D0, symbols=others)
    with db.transaction(pg, False):
        bars.upsert_bars(pg, [bars.make_bar("NVDA", D0, 1200, 1200, 1200, 1200, 1000)])
        dividends.upsert_dividends(pg, [Dividend("NVDA", D0, Decimal("1.000000"))])
    nvda = ("NVDA", (120.0, 121.0, 119.0, 120.5, 10_000.0))
    fake = FakeMassive(
        {D_WED: day(extra=[nvda]), D_THU: day(extra=[nvda]), D_FRI: day(extra=[nvda])},
        {D_THU: [Split("NVDA", D_THU, Decimal(1), Decimal(10))]},
        dividends_data={D_WED: [Dividend("NVDA", D_WED, Decimal("1.0"))]},
    )
    assert go(pg, fake) == 0
    assert stored_dividends(pg) == [
        ("NVDA", D0, Decimal("0.100000")),  # stored before: rewritten by apply_splits
        ("NVDA", D_WED, Decimal("0.100000")),  # fetched in the gap: adjusted in memory, not twice
    ]


def test_paper_held_symbol_outside_universe_gets_bars_and_dividends(pg, fixed_universe):
    seed(pg, D_THU)
    hold(pg, "GONE")
    hold(pg, "SOON", target_session=D_FRI)  # decided for the session being fetched
    hold(pg, "PAST", target_session=D_THU)  # an executed decision: not needed any more
    fake = FakeMassive(
        {D_FRI: day(extra=[GONE_BAR, ("SOON", (20.0, 21.0, 19.0, 20.5, 500.0)), ("PAST", (9.0, 9.0, 9.0, 9.0, 1.0))])},
        dividends_data={D_FRI: [Dividend("GONE", D_FRI, Decimal("0.4")), Dividend("PAST", D_FRI, Decimal("0.1"))]},
    )
    assert go(pg, fake) == 0
    stored = {r[0] for r in bars_on(pg, D_FRI)}
    assert stored == set(UNIVERSE) | {"GONE", "SOON"}  # not PAST, not ZZZZ
    assert stored_dividends(pg) == [("GONE", D_FRI, Decimal("0.400000"))]


def test_absent_paper_symbol_warns_and_does_not_count_toward_coverage(pg, fixed_universe, caplog):
    seed(pg, D_THU)
    for s in ("GONE1", "GONE2", "GONE3"):
        hold(pg, s)
    rows = day([s for s in UNIVERSE if s != "AVGO"])  # universe 9/10 = 90%; 3 held symbols all absent
    caplog.set_level(logging.WARNING)
    assert go(pg, FakeMassive({D_FRI: rows})) == 0
    assert "paper-held symbol(s) outside the universe absent" in caplog.text
    assert "GONE1, GONE2, GONE3" in caplog.text
    assert real_runs(pg)[0][1] == "success"


def test_dividends_failure_marks_run_failed_and_writes_nothing(pg, fixed_universe):
    seed(pg, D_THU)
    hold(pg, "GONE")
    before = checksums(pg)
    fake = FakeMassive({D_FRI: day(extra=[GONE_BAR])}, dividends_fail=MassiveError("dividends 2026-10-02: status 'ERROR'"))
    assert go(pg, fake) == 1
    [(_, status, _, _, error)] = real_runs(pg)
    assert status == "failed" and "dividends" in error
    assert bars_on(pg, D_FRI) == []
    assert stored_dividends(pg) == []
    assert q(pg, "SELECT count(*) FROM fx_rates") == [(0,)]
    after = checksums(pg)
    assert {k: v for k, v in after.items() if k != "runs"} == {k: v for k, v in before.items() if k != "runs"}


def test_fx_failure_after_dividends_fetched_writes_no_dividends(pg, fixed_universe):
    seed(pg, D_THU)

    def fx_down():
        raise RuntimeError("frankfurter down")

    fake = FakeMassive({D_FRI: day()}, dividends_data={D_FRI: [Dividend("SPY", D_FRI, Decimal("1.888834"))]})
    assert nightly.execute(pg, now=FRI_NIGHT, client=fake, fetch_fx=fx_down) == 1
    assert real_runs(pg)[0][1] == "failed"
    assert stored_dividends(pg) == []
    assert bars_on(pg, D_FRI) == []


# ---- CLI surface ----

def test_parse_now_accepts_z_and_naive_as_utc():
    assert nightly._parse_now("2026-10-02T23:00:00Z") == FRI_NIGHT
    assert nightly._parse_now("2026-10-02T23:00:00") == FRI_NIGHT
    assert nightly._parse_now("2026-10-03T06:00:00+07:00") == FRI_NIGHT
    with pytest.raises(argparse.ArgumentTypeError):
        nightly._parse_now("friday")


def test_add_arguments_and_run_wiring(monkeypatch):
    p = argparse.ArgumentParser()
    nightly.add_arguments(p)
    args = p.parse_args(["--now", "2026-10-02T23:00:00Z"])
    args.dry_run = True

    class DummyConn:
        closed = False

        def close(self):
            self.closed = True

    conn = DummyConn()
    seen = {}

    def fake_execute(c, **kw):
        seen.update(kw, conn=c)
        return 0

    monkeypatch.setattr(nightly.config, "require", lambda name: "sekret")
    monkeypatch.setattr(nightly.db, "connect", lambda: conn)
    monkeypatch.setattr(nightly, "execute", fake_execute)
    assert nightly.run(args) == 0
    assert seen["conn"] is conn and conn.closed
    assert seen["now"] == FRI_NIGHT and seen["dry_run"] is True and seen["secret"] == "sekret"


def test_run_without_key_exits_2(monkeypatch):
    def missing(name):
        raise nightly.config.ConfigError(f"{name} is not set")

    monkeypatch.setattr(nightly.config, "require", missing)
    args = argparse.Namespace(now=None, dry_run=False)
    assert nightly.run(args) == 2
