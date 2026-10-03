"""`backtest_wf` command: discovery, write_wf_report, the tuning loop, preconditions, and an
end-to-end run on a synthetic schema."""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, cli, config, dates, db, fx
from seer_engine.backtest import io as bio
from seer_engine.backtest import walkforward, wf_report
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.tuning import IS_START
from seer_engine.commands import backtest_wf as cmd
from seer_engine.strategies import a2 as strategy_a2
from seer_engine.strategies.base import history_from_bars

SESSIONS = dates.sessions(date(2022, 1, 3), date(2024, 6, 28))
IS_S = SESSIONS[200]  # 2022-10-19; data_date SESSIONS[199] is the 200th bar
FIRST_YEAR = 2023  # folds 2023 and 2024
END = SESSIONS[-1]  # 2024-06-28
OLD_LAST = SESSIONS[560]  # OLD's bars end in 2024 (delisted while a member)
DIVIDEND_DAY = SESSIONS[600]  # inside the traded window
FX_LATE = SESSIONS[400]
TRADED = ("AAA", "BBB", "CCC", "DDD")
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


def synthetic_bars(*, with_spy: bool = True) -> list:
    rows = []
    for k, symbol in enumerate(TRADED):
        rows += [bars.make_bar(symbol, d, *v) for d, v in zip(SESSIONS, ohlcv(k, len(SESSIONS)))]
    if with_spy:
        rows += [bars.make_bar("SPY", d, *v) for d, v in zip(SESSIONS, ohlcv(6, len(SESSIONS)))]
    old_sessions = [d for d in SESSIONS if d <= OLD_LAST]
    rows += [bars.make_bar("OLD", d, *v) for d, v in zip(old_sessions, ohlcv(7, len(old_sessions)))]
    return rows


EXPECTED_ROWS = (len(TRADED) + 1) * len(SESSIONS) + len([d for d in SESSIONS if d <= OLD_LAST])


def seed(conn, *, with_bars=True, with_spy=True, fx_rows=((SESSIONS[0], "16000"), (FX_LATE, "16250.5"))):
    with db.transaction(conn, False):
        if with_bars:
            bars.upsert_bars(conn, synthetic_bars(with_spy=with_spy))
        with conn.cursor() as cur:
            members = [(s, "SP500") for s in (*TRADED, "OLD", "GONE")] + [("AAA", "NDX")]
            cur.executemany(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, %s, %s, NULL, %s)",
                [(s, i, LONG_AGO, s) for s, i in members],
            )
        fx.upsert_fx(conn, list(fx_rows))


def in_memory_market() -> Market:
    """The same data as seed(), without a database (SPY not a member, GONE has no bars)."""
    by_symbol: dict[str, list] = {}
    for b in synthetic_bars():
        by_symbol.setdefault(b.symbol, []).append(b)
    history = {s: history_from_bars(s, rows) for s, rows in sorted(by_symbol.items())}
    intervals = tuple(sorted((s, LONG_AGO, None) for s in (*TRADED, "OLD", "GONE")))
    return Market(
        history=history,
        membership=Membership(intervals=intervals),
        fx=((SESSIONS[0], Decimal("16000")), (FX_LATE, Decimal("16250.5"))),
    )


def write_dividends(tmp_path):
    path = tmp_path / "spy_dividends.csv"
    path.write_text(f"ex_date,amount_usd\n{DIVIDEND_DAY.isoformat()},0.75\n", encoding="utf-8")
    return path


def argv(tmp_path, out_name="out", *extra):
    return [
        "backtest_wf",
        "--out", str(tmp_path / out_name),
        "--cache-dir", str(tmp_path / "cache"),
        "--is-start", IS_S.isoformat(),
        "--first-year", str(FIRST_YEAR),
        "--end", END.isoformat(),
        "--dividends", str(tmp_path / "spy_dividends.csv"),
        *extra,
    ]


def file_names(stem: str) -> list[str]:
    return [
        f"{stem}.md",
        f"{stem}-equity.csv",
        f"{stem}-equity.svg",
        f"{stem}-variants.svg",
        f"{stem}-grid.csv",
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
    assert "backtest_wf" in cli.discover()
    args = cli.build_parser().parse_args(["backtest_wf"])
    assert args._run is cmd.run
    assert args.out == cmd.DEFAULT_OUT == config.REPO_ROOT / "docs" / "backtests"
    assert args.cache_dir == bio.CACHE_DIR == config.REPO_ROOT / "engine" / ".cache"
    assert args.dividends == bio.DIVIDENDS_CSV == config.REPO_ROOT / "engine" / "data" / "spy_dividends.csv"
    assert (args.is_start, args.first_year, args.end) == (IS_START, walkforward.FIRST_TRADE_YEAR, None)
    assert args.refresh_cache is False
    assert cmd.HELP


@pytest.mark.parametrize(
    "extra",
    [
        ["--end", "2026-13-01"],
        ["--is-start", "yesterday"],
        ["--first-year", "twenty"],
    ],
)
def test_bad_argument_is_a_usage_error(extra):
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["backtest_wf", *extra])
    assert exc.value.code == 2


def test_write_wf_report_writes_five_files_in_order_with_lf(tmp_path, monkeypatch):
    texts = {
        "render_markdown": "# md\nline\n",
        "equity_csv": "date,walk_forward\n",
        "equity_svg": "<svg>equity</svg>\n",
        "variants_svg": "<svg>variants</svg>\n",
        "grid_csv": "fold,combo\n",
    }
    for name, text in texts.items():
        monkeypatch.setattr(wf_report, name, lambda report, _t=text: _t)
    report = SimpleNamespace(data_end=date(2024, 6, 28))
    paths = bio.write_wf_report(tmp_path / "nested" / "out", report)
    stem = wf_report.report_stem(date(2024, 6, 28))
    assert stem == "2024-06-28-strategy-a2-walkforward"
    assert [p.name for p in paths] == file_names(stem)
    assert [p.read_bytes() for p in paths] == [t.encode("utf-8") for t in texts.values()]


def test_write_wf_report_renders_everything_before_writing(tmp_path, monkeypatch):
    for name in ("render_markdown", "equity_csv", "equity_svg", "variants_svg"):
        monkeypatch.setattr(wf_report, name, lambda report: "ok\n")

    def boom(report):
        raise RuntimeError("grid render failed")

    monkeypatch.setattr(wf_report, "grid_csv", boom)
    with pytest.raises(RuntimeError, match="grid render failed"):
        bio.write_wf_report(tmp_path / "out", SimpleNamespace(data_end=date(2024, 6, 28)))
    assert not (tmp_path / "out").exists()


def test_tune_all_equals_one_tune_call_and_logs_each_run(caplog):
    market = in_memory_market()
    strategy = strategy_a2.STRATEGY_A2
    prepared = strategy.prepare(market.history)
    folds = walkforward.folds(IS_S, FIRST_YEAR, END)
    combos = walkforward.combinations()[::54]  # 6 combinations, every variant represented
    assert {c.variant for c in combos} == set(strategy_a2.VARIANTS)
    caplog.set_level(logging.INFO)

    stitched = cmd.tune_all(market, strategy, prepared, combos, folds)

    assert stitched == walkforward.tune(market, strategy, prepared, combos, folds)
    assert len(stitched) == len(folds) == 2
    assert all([r.params for r in rows] == list(combos) for rows in stitched)
    messages = [r.getMessage() for r in caplog.records]
    assert [m.split(" ", 2)[1] for m in messages if m.startswith("tune ")] == [
        f"{i}/{len(combos)}" for i in range(1, len(combos) + 1)
    ]
    assert sum(1 for m in messages if m.startswith(f"tune: {len(combos)} runs on ")) == 1


# ---- preconditions (exit 2, nothing written) -----------------------------------------------


def test_empty_bars_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, with_bars=False)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert not (tmp_path / "out").exists()


def test_no_spy_bars_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, with_spy=False)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "extra",
    [
        ["--end", dates.next_session(END).isoformat()],  # after the last SPY bar
        ["--end", date(2023, 6, 10).isoformat()],  # a Saturday
        ["--is-start", date(2022, 10, 22).isoformat()],  # a Saturday
        ["--first-year", "2022"],  # fold 2022 would tune on nothing before is_start
        ["--first-year", "2025"],  # no fold: 2025's first session is after --end
    ],
)
def test_bad_windows_exit_2(pg, point_cli_at, tmp_path, extra):
    seed(pg)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path, "out", *extra)) == 2
    assert not (tmp_path / "out").exists()


def test_no_fx_before_is_start_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, fx_rows=((FX_LATE, "16250.5"),))
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert not (tmp_path / "out").exists()


def test_missing_dividends_file_exits_2(pg, point_cli_at, tmp_path):
    seed(pg)
    assert cli.main(argv(tmp_path)) == 2  # no spy_dividends.csv written
    assert not (tmp_path / "out").exists()


# ---- end to end ------------------------------------------------------------------------------


def test_end_to_end_report_read_only_cache_hit_and_byte_identical_rerun(
    pg, point_cli_at, tmp_path, monkeypatch, caplog
):
    seed(pg)
    write_dividends(tmp_path)
    caplog.set_level(logging.INFO)
    captured = []
    real_write = bio.write_wf_report

    def capturing_write(out_dir, report):
        captured.append(report)
        return real_write(out_dir, report)

    monkeypatch.setattr(bio, "write_wf_report", capturing_write)
    before = checksums(pg)

    assert cli.main(argv(tmp_path, "out1")) == 0

    assert checksums(pg) == before  # read-only
    stem = f"{END.isoformat()}-strategy-a2-walkforward"
    assert wf_report.report_stem(END) == stem
    names = file_names(stem)
    assert sorted(p.name for p in (tmp_path / "out1").iterdir()) == sorted(names)
    assert [p.name for p in (tmp_path / "cache").iterdir()] == [
        f"bars-{END.isoformat()}-{EXPECTED_ROWS}.pkl"
    ]

    [report] = captured
    combos = walkforward.combinations()
    folds = walkforward.folds(IS_S, FIRST_YEAR, END)
    assert report.data_end == END
    assert report.bars_rows == EXPECTED_ROWS
    assert report.symbols_with_bars == len(TRADED) + 2  # + SPY + OLD
    assert report.never_fetched_members == 1  # GONE
    assert report.is_start == IS_S
    assert report.folds == folds
    assert [f.year for f in report.folds] == [2023, 2024]
    assert len(report.fold_rows) == 2
    for rows in report.fold_rows:
        assert [r.params for r in rows] == list(combos)
    assert report.combined.name == walkforward.COMBINED
    assert [v.name for v in report.variants] == list(strategy_a2.VARIANTS)
    for wf in (report.combined, *report.variants):
        assert wf.folds == folds
        assert len(wf.selections) == len(folds)
        assert (wf.run.start, wf.run.end) == (folds[0].trade_start, END)
    for v, wf in zip(strategy_a2.VARIANTS, report.variants):
        assert all(s.params.variant == v for s in wf.selections)
    for curve in (report.spy_price, report.spy_tr):
        assert curve.snapshots[0].date == report.combined.run.snapshots[0].date
        assert curve.snapshots[-1].date == END
    assert report.spy_tr.dividends_usd > 0
    assert [g.year for g in report.survivorship] == [2022, 2023, 2024]
    assert report.frozen_params == strategy_a2.STRATEGY_A2_PARAMS

    md = (tmp_path / "out1" / f"{stem}.md").read_text(encoding="utf-8")
    assert report.verdict.sentence in md
    assert wf_report.parse_machine_line(md, wf_report.GATE_KEY) == (
        "passed" if report.verdict.passed else "failed"
    )
    frozen_line = json.loads(wf_report.parse_machine_line(md, wf_report.FROZEN_KEY))
    if report.frozen_params is None:
        assert frozen_line is None
    else:
        assert isinstance(frozen_line, dict)
    last_fold = json.loads(wf_report.parse_machine_line(md, wf_report.LAST_FOLD_KEY))
    assert isinstance(last_fold, dict)
    assert last_fold["variant"] == report.combined.selections[-1].params.variant

    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("prepared Strategy A2 features for ") for m in messages)
    assert sum(1 for m in messages if m.startswith("tune ") and f"/{len(combos)} " in m) == len(combos)
    assert sum(1 for m in messages if m.startswith(f"tune: {len(combos)} runs on ")) == 1
    for name in (walkforward.COMBINED, *strategy_a2.VARIANTS):
        assert sum(1 for m in messages if m.startswith(f"{name} fold ")) == len(folds)
    assert any(m.startswith("gate ") and report.verdict.sentence in m for m in messages)
    assert any("STRATEGY_A2_PARAMS" in m for m in messages)
    assert sum(1 for m in messages if m.startswith("wrote ")) == len(names)

    # Second run: the cache must be used (no COPY) and every file byte-identical.
    def no_copy(conn):
        raise AssertionError("the bars cache should have been used")

    monkeypatch.setattr(bio, "read_bars_frame", no_copy)
    caplog.clear()
    assert cli.main(argv(tmp_path, "out2")) == 0
    assert any(r.getMessage().startswith("bars cache hit") for r in caplog.records)
    for name in names:
        assert (tmp_path / "out2" / name).read_bytes() == (tmp_path / "out1" / name).read_bytes(), name
    assert captured[1].fold_rows == captured[0].fold_rows
    assert captured[1].combined.selections == captured[0].combined.selections
    assert [v.selections for v in captured[1].variants] == [v.selections for v in captured[0].variants]
    assert captured[1].verdict == captured[0].verdict
    assert checksums(pg) == before
