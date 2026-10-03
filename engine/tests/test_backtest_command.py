"""`backtest` command: discovery, preconditions, and an end-to-end run on a synthetic schema."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, cli, config, dates, db, fx
from seer_engine.backtest import io as bio
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.tuning import IS_START, OOS_START, grid
from seer_engine.commands import backtest as cmd
from seer_engine.strategies import a as strategy_a
from seer_engine.strategies.base import history_from_bars

SESSIONS = dates.sessions(date(2024, 1, 2), date(2025, 3, 31))[:250]
IS_S = SESSIONS[200]  # data_date SESSIONS[199] is the 200th bar
OOS_S = SESSIONS[225]
END = SESSIONS[249]
OLD_LAST = SESSIONS[230]  # OLD's bars end mid-OOS (delisted while a member)
DIVIDEND_DAY = SESSIONS[235]
TRADED = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")
LONG_AGO = date(2015, 1, 2)


def ohlcv(k: int, n: int) -> list[tuple[float, float, float, float, int]]:
    """Rising sawtooth: +0.6 %/session, two -4 % sessions then +6 % every 12; phase shifted by k."""
    price = 40.0 + 7.0 * k
    out = []
    for i in range(n):
        phase = (i + 3 * k) % 12
        if phase in (9, 10):
            price *= 0.96
        elif phase == 11:
            price *= 1.06
        else:
            price *= 1.006
        c = round(price, 4)
        out.append((round(c * 0.999, 4), round(c * 1.02, 4), round(c * 0.97, 4), c, 2_000_000 + 1_000 * k))
    return out


def synthetic_bars() -> list:
    rows = []
    for k, symbol in enumerate(TRADED):
        rows += [bars.make_bar(symbol, d, *v) for d, v in zip(SESSIONS, ohlcv(k, len(SESSIONS)))]
    rows += [bars.make_bar("SPY", d, *v) for d, v in zip(SESSIONS, ohlcv(6, len(SESSIONS)))]
    old_sessions = [d for d in SESSIONS if d <= OLD_LAST]
    rows += [bars.make_bar("OLD", d, *v) for d, v in zip(old_sessions, ohlcv(7, len(old_sessions)))]
    return rows


EXPECTED_ROWS = 7 * len(SESSIONS) + len([d for d in SESSIONS if d <= OLD_LAST])


def seed(conn, *, with_bars=True, fx_rows=((SESSIONS[0], "16000"), (SESSIONS[210], "16250.5"))):
    with db.transaction(conn, False):
        if with_bars:
            bars.upsert_bars(conn, synthetic_bars())
        with conn.cursor() as cur:
            members = [(s, "SP500") for s in (*TRADED, "OLD", "GONE")] + [("AAA", "NDX")]
            cur.executemany(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, %s, %s, NULL, %s)",
                [(s, i, LONG_AGO, s) for s, i in members],
            )
        fx.upsert_fx(conn, list(fx_rows))


def write_dividends(tmp_path):
    path = tmp_path / "spy_dividends.csv"
    path.write_text(f"ex_date,amount_usd\n{DIVIDEND_DAY.isoformat()},0.75\n", encoding="utf-8")
    return path


def argv(tmp_path, out_name="out", *extra):
    return [
        "backtest",
        "--out", str(tmp_path / out_name),
        "--cache-dir", str(tmp_path / "cache"),
        "--is-start", IS_S.isoformat(),
        "--oos-start", OOS_S.isoformat(),
        "--end", END.isoformat(),
        "--dividends", str(tmp_path / "spy_dividends.csv"),
        *extra,
    ]


def checksums(conn):
    out = {}
    for table, order in {
        "bars": "x.symbol, x.date",
        "universe": "x.index_id, x.symbol, x.start_date",
        "fx_rates": "x.date",
        "strategies": "x.id",
        "runs": "x.id",
        "orders": "x.id",
        "equity_snapshots": "x.strategy_id, x.date",
    }.items():
        with conn.cursor(row_factory=tuple_row) as cur:
            cur.execute(
                f"SELECT count(*), coalesce(md5(string_agg(x::text, '|' ORDER BY {order})), '') "
                f"FROM {table} x"
            )
            out[table] = cur.fetchone()
    conn.rollback()
    return out


@pytest.fixture
def point_cli_at(pg_schema, monkeypatch):
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", pg_schema.url)


# ---- no database -----------------------------------------------------------------------------


def test_discovered_with_defaults():
    assert "backtest" in cli.discover()
    args = cli.build_parser().parse_args(["backtest"])
    assert args._run is cmd.run
    assert args.out == config.REPO_ROOT / "docs" / "backtests"
    assert args.cache_dir == bio.CACHE_DIR == config.REPO_ROOT / "engine" / ".cache"
    assert args.dividends == bio.DIVIDENDS_CSV == config.REPO_ROOT / "engine" / "data" / "spy_dividends.csv"
    assert (args.is_start, args.oos_start, args.end) == (IS_START, OOS_START, None)
    assert args.refresh_cache is False
    assert cmd.HELP


def test_bad_date_argument_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["backtest", "--end", "2026-13-01"])
    assert exc.value.code == 2


def test_never_fetched_members_counts_window_members_without_bars():
    aaa = history_from_bars("AAA", [bars.make_bar("AAA", date(2024, 1, 2), 1, 1, 1, 1, 1)])
    market = Market(
        history={"AAA": aaa},
        membership=Membership(
            intervals=(
                ("AAA", date(2015, 1, 2), None),  # has bars
                ("GONE", date(2015, 1, 2), date(2020, 1, 2)),  # left before the window
                ("LATE", date(2025, 1, 2), None),  # joined after the window
                ("MISS", date(2019, 1, 2), date(2024, 6, 3)),  # overlaps, no bars
            )
        ),
        fx=(),
    )
    assert cmd.never_fetched_members(market, date(2021, 1, 4), date(2024, 12, 31)) == 1


# ---- preconditions (exit 2, nothing written) -----------------------------------------------


def test_empty_bars_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, with_bars=False)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "extra",
    [
        ["--end", dates.next_session(END).isoformat()],  # after the last SPY bar
        ["--oos-start", date(2024, 12, 7).isoformat()],  # a Saturday
        ["--oos-start", IS_S.isoformat()],  # is_start == oos_start
    ],
)
def test_bad_windows_exit_2(pg, point_cli_at, tmp_path, extra):
    seed(pg)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path, "out", *extra)) == 2
    assert not (tmp_path / "out").exists()


def test_no_fx_before_is_start_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, fx_rows=((SESSIONS[210], "16250.5"),))
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2


def test_missing_dividends_file_exits_2(pg, point_cli_at, tmp_path):
    seed(pg)
    assert cli.main(argv(tmp_path)) == 2  # no spy_dividends.csv written


# ---- end to end ------------------------------------------------------------------------------


def test_end_to_end_report_verdict_read_only_and_byte_identical_rerun(
    pg, point_cli_at, tmp_path, monkeypatch, caplog
):
    seed(pg)
    write_dividends(tmp_path)
    caplog.set_level(logging.INFO)
    captured = []
    real_write = bio.write_report

    def capturing_write(out_dir, report):
        captured.append(report)
        return real_write(out_dir, report)

    monkeypatch.setattr(bio, "write_report", capturing_write)
    before = checksums(pg)

    assert cli.main(argv(tmp_path, "out1")) == 0

    assert checksums(pg) == before  # read-only
    stem = f"{END.isoformat()}-strategy-a"
    names = [f"{stem}.md", f"{stem}-equity.csv", f"{stem}-equity.svg"]
    assert sorted(p.name for p in (tmp_path / "out1").iterdir()) == sorted(names)
    assert [p.name for p in (tmp_path / "cache").iterdir()] == [
        f"bars-{END.isoformat()}-{EXPECTED_ROWS}.pkl"
    ]

    [report] = captured
    assert report.data_end == END
    assert report.bars_rows == EXPECTED_ROWS
    assert report.symbols_with_bars == len(TRADED) + 2  # + SPY + OLD
    assert [r.params for r in report.grid_rows] == list(grid())
    assert report.selection.params in [r.params for r in report.grid_rows]
    assert report.frozen_params == strategy_a.STRATEGY_A_PARAMS
    assert report.never_fetched_members == 1  # GONE
    windows = (report.in_sample, report.out_of_sample, report.full)
    assert [w.name for w in windows] == ["In-sample", "Out-of-sample", "Full window"] == list(cmd.WINDOW_NAMES)
    assert [(w.run.start, w.run.end) for w in windows] == [
        (IS_S, dates.prev_session(OOS_S)),
        (OOS_S, END),
        (IS_S, END),
    ]
    for w in windows:
        assert w.run.params == report.selection.params
        assert w.spy_price.snapshots[0].date == w.spy_tr.snapshots[0].date == w.run.snapshots[0].date
        assert w.spy_price.snapshots[-1].date == w.spy_tr.snapshots[-1].date == w.run.end
    assert report.in_sample.spy_tr.dividends_usd == Decimal("0")
    assert report.out_of_sample.spy_tr.dividends_usd > 0
    assert report.verdict.sentence in (tmp_path / "out1" / f"{stem}.md").read_text(encoding="utf-8")

    messages = [r.getMessage() for r in caplog.records]
    assert sum(1 for m in messages if m.startswith("grid ") and f"/{len(grid())} " in m) == len(grid())
    assert any(m.startswith(f"grid: {len(grid())} runs on ") for m in messages)
    assert any(m.startswith("gate ") and report.verdict.sentence in m for m in messages)
    assert any("STRATEGY_A_PARAMS" in m for m in messages)

    # Second run: the cache must be used (no COPY) and every file byte-identical.
    def no_copy(conn):
        raise AssertionError("the bars cache should have been used")

    monkeypatch.setattr(bio, "read_bars_frame", no_copy)
    caplog.clear()
    assert cli.main(argv(tmp_path, "out2")) == 0
    assert any(r.getMessage().startswith("bars cache hit") for r in caplog.records)
    for name in names:
        assert (tmp_path / "out2" / name).read_bytes() == (tmp_path / "out1" / name).read_bytes(), name
    assert captured[1].selection == captured[0].selection
    assert checksums(pg) == before
