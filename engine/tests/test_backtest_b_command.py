"""`backtest_b` command: discovery, the two io writers, execute's determinism and contents,
wall times in logs only, A2's curve against backtest_wf's, the artifact on a pass only,
preconditions (exit 2), and an end-to-end run on a synthetic schema.

The synthetic market has one fold (2023) so that A2's 324-combination tuning pass covers about
50 sessions. Fold 2023 still trains on more than 2 x min_samples_leaf rows, so the trees split.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, cli, config, dates, db, fx
from seer_engine.backtest import b_report
from seer_engine.backtest import b_walkforward as bw
from seer_engine.backtest import io as bio
from seer_engine.backtest import walkforward
from seer_engine.backtest.benchmark import parse_dividends
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.metrics import curve_metrics, run_metrics
from seer_engine.backtest.tuning import IS_START
from seer_engine.commands import backtest_b as cmd
from seer_engine.commands import backtest_wf as cmd_wf
from seer_engine.strategies import b as strategy_b
from seer_engine.strategies import b_model
from seer_engine.strategies.base import history_from_bars

SESSIONS = dates.sessions(date(2022, 1, 3), date(2023, 6, 30))
IS_S = SESSIONS[200]  # 2022-10-19: data_date SESSIONS[199] is the 200th bar
FIRST_YEAR = 2023  # one fold: train through 2022-12-30, trade 2023-01-03..END
END = SESSIONS[-1]  # 2023-06-30
FX_LATE = SESSIONS[300]
DIVIDEND_DAY = SESSIONS[320]  # inside the traded window
TRADED = tuple(f"S{k:02d}" for k in range(16))
SPY_K = 20
LONG_AGO = date(2015, 1, 2)
STEM = f"{END.isoformat()}-strategy-b-walkforward"
FILE_NAMES = [f"{STEM}.md", f"{STEM}-equity.csv", f"{STEM}-equity.svg"]
ARTIFACT_NAME = f"{END.isoformat()}-strategy-b.pkl"
DIVIDENDS_TEXT = f"ex_date,amount_usd\n{DIVIDEND_DAY.isoformat()},0.75\n"
DIVIDENDS = parse_dividends(DIVIDENDS_TEXT)
EXPECTED_ROWS = (len(TRADED) + 1) * len(SESSIONS)
DURATION = re.compile(r"\((\d+\.\d{2})s\)")

# Messages execute must log, each with its wall time "(N.NNs)".
TIMED_PREFIXES = (
    "prepared Strategy B features: ",
    "candidate table: ",
    f"{bw.B}: 1 fold model(s) fitted ",
    f"{bw.B_LINEAR}: 1 fold model(s) fitted ",
    "determinism probe on fold 2023: ",
    "A2 recompute: prepared Strategy A2 features ",
    "A2 recompute: done ",
    "SPY ",
    "survivorship: ",
    f"{bw.B} passed nights: ",
    f"{bw.B_LINEAR} passed nights: ",
    f"{bw.B} calibration: ",
    f"{bw.B_LINEAR} calibration: ",
    "gate ",
    "execute: done ",
)


def ohlcv(k: int, n: int) -> list[tuple[float, float, float, float, int]]:
    """A rising sawtooth whose cycle length, drift, phase and volume depend on k, so features
    and labels vary across symbols and dates. Close >= ~30 and volume >= 2M keep every symbol
    above the $20M liquidity floor."""
    price = 30.0 + 2.5 * k
    cycle = 9 + k % 5
    drift = 1.004 + 0.0005 * (k % 4)
    out = []
    for i in range(n):
        phase = (i + 2 * k) % cycle
        if phase in (cycle - 3, cycle - 2):
            price *= 0.965
        elif phase == cycle - 1:
            price *= 1.05
        else:
            price *= drift
        c = round(price, 4)
        o = round(c * (0.995 + 0.001 * (phase % 3)), 4)
        out.append((o, round(c * 1.018, 4), round(c * 0.972, 4), c, 2_000_000 + 25_000 * k + 40_000 * phase))
    return out


def synthetic_bars(*, with_spy: bool = True) -> list:
    rows = []
    for k, symbol in enumerate(TRADED):
        rows += [bars.make_bar(symbol, d, *v) for d, v in zip(SESSIONS, ohlcv(k, len(SESSIONS)))]
    if with_spy:
        rows += [bars.make_bar("SPY", d, *v) for d, v in zip(SESSIONS, ohlcv(SPY_K, len(SESSIONS)))]
    return rows


def in_memory_market() -> Market:
    """The same data as seed(), without a database (SPY not a member, GONE has no bars)."""
    by_symbol: dict[str, list] = {}
    for b in synthetic_bars():
        by_symbol.setdefault(b.symbol, []).append(b)
    history = {s: history_from_bars(s, rows) for s, rows in sorted(by_symbol.items())}
    intervals = tuple(sorted((s, LONG_AGO, None) for s in (*TRADED, "GONE")))
    return Market(
        history=history,
        membership=Membership(intervals=intervals),
        fx=((SESSIONS[0], Decimal("16000")), (FX_LATE, Decimal("16250.5"))),
    )


def seed(conn, *, with_bars=True, with_spy=True, fx_rows=((SESSIONS[0], "16000"), (FX_LATE, "16250.5"))):
    with db.transaction(conn, False):
        if with_bars:
            bars.upsert_bars(conn, synthetic_bars(with_spy=with_spy))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, %s, %s, NULL, %s)",
                [(s, "SP500", LONG_AGO, s) for s in (*TRADED, "GONE")],
            )
        fx.upsert_fx(conn, list(fx_rows))


def write_dividends(tmp_path):
    path = tmp_path / "spy_dividends.csv"
    path.write_text(DIVIDENDS_TEXT, encoding="utf-8")
    return path


def argv(tmp_path, *extra):
    return [
        "backtest_b",
        "--out", str(tmp_path / "out"),
        "--cache-dir", str(tmp_path / "cache"),
        "--model-dir", str(tmp_path / "models"),
        "--is-start", IS_S.isoformat(),
        "--first-year", str(FIRST_YEAR),
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


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _fake_clock(step: float = 1000.0) -> SimpleNamespace:
    """A perf_counter that advances ``step`` seconds per call: every logged duration >= step."""
    state = {"t": 0.0}

    def perf_counter() -> float:
        state["t"] += step
        return state["t"]

    return SimpleNamespace(perf_counter=perf_counter)


def _execute_logged() -> tuple[object, list[str]]:
    handler = _ListHandler()
    logger = logging.getLogger("seer_engine")
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        report = cmd.execute(in_memory_market(), EXPECTED_ROWS, DIVIDENDS, IS_S, FIRST_YEAR, END)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
    return report, handler.messages


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """execute twice on fresh copies of the same market: once on the real clock, once on fake
    clocks in backtest_b and backtest_wf (1000 s per reading). Both report sets are written."""
    first, first_logs = _execute_logged()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cmd, "time", _fake_clock())
        mp.setattr(cmd_wf, "time", _fake_clock())
        second, second_logs = _execute_logged()
    paths1 = bio.write_b_report(tmp_path_factory.mktemp("b-out1"), first)
    paths2 = bio.write_b_report(tmp_path_factory.mktemp("b-out2"), second)
    return SimpleNamespace(
        first=first,
        second=second,
        first_logs=first_logs,
        second_logs=second_logs,
        paths1=paths1,
        paths2=paths2,
    )


def _stand_in(base, *, passed: bool, gated: str, frozen=None) -> SimpleNamespace:
    """What run() reads from a report, with the verdict and gated curve chosen by the test and
    the real fold models of ``base``. A stand-in, so no BReport invariant is bypassed."""
    return SimpleNamespace(
        data_end=END,
        verdict=SimpleNamespace(passed=passed, sentence="stand-in verdict"),
        gated=gated,
        b=base.b,
        b_linear=base.b_linear,
        frozen=frozen,
    )


def _patch_run(monkeypatch, report) -> tuple[list, list]:
    seen: list = []
    calls: list = []

    def fake_execute(market, bars_rows, dividends, is_start, first_year, end):
        seen.append((bars_rows, dividends, is_start, first_year, end))
        return report

    def fake_write(out_dir, rep):
        calls.append((Path(out_dir), rep))
        return [Path(out_dir) / name for name in FILE_NAMES]

    monkeypatch.setattr(cmd, "execute", fake_execute)
    monkeypatch.setattr(bio, "write_b_report", fake_write)
    return seen, calls


# ---- no database -----------------------------------------------------------------------------


def test_discovered_with_defaults():
    assert "backtest_b" in cli.discover()
    args = cli.build_parser().parse_args(["backtest_b"])
    assert args._run is cmd.run
    assert args.out == cmd.DEFAULT_OUT == cmd_wf.DEFAULT_OUT == config.REPO_ROOT / "docs" / "backtests"
    assert args.model_dir == bio.MODELS_DIR == config.REPO_ROOT / "engine" / "data" / "models"
    assert args.cache_dir == bio.CACHE_DIR
    assert args.dividends == bio.DIVIDENDS_CSV
    assert (args.is_start, args.first_year, args.end) == (IS_START, walkforward.FIRST_TRADE_YEAR, None)
    assert args.refresh_cache is False
    assert cmd.HELP


def test_help_lists_every_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["backtest_b", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in (
        "--out", "--cache-dir", "--refresh-cache", "--is-start",
        "--first-year", "--end", "--dividends", "--model-dir",
    ):
        assert flag in out, flag


def test_write_b_report_writes_three_files_in_order_with_lf(tmp_path, monkeypatch):
    texts = {
        "render_markdown": "# md\nline\n",
        "equity_csv": b_report.EQUITY_CSV_HEADER + "\n",
        "equity_svg": "<svg>equity</svg>\n",
    }
    for name, text in texts.items():
        monkeypatch.setattr(b_report, name, lambda report, _t=text: _t)
    paths = bio.write_b_report(tmp_path / "nested" / "out", SimpleNamespace(data_end=END))
    assert b_report.report_stem(END) == STEM
    assert [p.name for p in paths] == FILE_NAMES
    assert [p.read_bytes() for p in paths] == [t.encode("utf-8") for t in texts.values()]


def test_write_b_report_renders_everything_before_writing(tmp_path, monkeypatch):
    for name in ("render_markdown", "equity_csv"):
        monkeypatch.setattr(b_report, name, lambda report: "ok\n")

    def boom(report):
        raise RuntimeError("svg render failed")

    monkeypatch.setattr(b_report, "equity_svg", boom)
    with pytest.raises(RuntimeError, match="svg render failed"):
        bio.write_b_report(tmp_path / "out", SimpleNamespace(data_end=END))
    assert not (tmp_path / "out").exists()


def test_write_model_artifact_writes_dumps_and_returns_its_sha256(tmp_path):
    X = np.array([[0.0, 1.0], [1.0, 0.0], [2.0, 1.0], [3.0, 3.0], [4.0, 2.0]], dtype=np.float64)
    y = np.array([0.01, -0.02, 0.03, 0.05, 0.02], dtype=np.float64)
    model = b_model.fit_ridge(X, y)
    model_dir = tmp_path / "models" / "deep"

    path, digest = bio.write_model_artifact(model_dir, END, model)

    assert path == model_dir / ARTIFACT_NAME
    data = path.read_bytes()
    assert data == b_model.dumps(model)
    assert digest == hashlib.sha256(data).hexdigest() == b_model.sha256(data)
    assert b_model.loads(data) == model
    assert [p.name for p in model_dir.iterdir()] == [ARTIFACT_NAME]  # no temp file left behind
    assert bio.write_model_artifact(model_dir, END, model) == (path, digest)
    assert path.read_bytes() == data
    with pytest.raises(TypeError):
        bio.write_model_artifact(model_dir, END, "not a model")


def test_execute_twice_is_equal_and_byte_identical(runs):
    assert runs.first == runs.second
    assert [p.name for p in runs.paths1] == FILE_NAMES
    assert [p.name for p in runs.paths2] == FILE_NAMES
    for p1, p2 in zip(runs.paths1, runs.paths2):
        assert p1.read_bytes() == p2.read_bytes(), p1.name
    md = runs.paths1[0].read_text(encoding="utf-8")
    assert runs.first.verdict.sentence in md
    assert b_report.parse_machine_line(md, b_report.GATE_KEY) == (
        "passed" if runs.first.verdict.passed else "failed"
    )
    assert b_report.parse_machine_line(md, b_report.GATED_KEY) == runs.first.gated


def test_execute_report_fields(runs):
    r = runs.first
    folds = walkforward.folds(IS_S, FIRST_YEAR, END)
    assert r.data_end == END
    assert r.bars_rows == EXPECTED_ROWS
    assert r.symbols_with_bars == len(TRADED) + 1  # + SPY
    assert r.never_fetched_members == 1  # GONE
    assert [g.year for g in r.survivorship] == [2022, 2023]
    assert r.is_start == IS_S
    assert r.folds == folds
    assert 0 < r.labelled_rows <= r.candidate_rows
    assert r.gated == (bw.B if r.determinism_ok else bw.B_LINEAR)
    assert (r.b.name, r.b_linear.name) == (bw.B, bw.B_LINEAR)
    min_rows = 2 * b_model.TREE_PARAMS["min_samples_leaf"]
    for wf, kind in ((r.b, b_model.TREE), (r.b_linear, b_model.RIDGE)):
        assert wf.folds == folds
        assert [fm.fold for fm in wf.fold_models] == list(folds)
        assert all(fm.model.kind == kind for fm in wf.fold_models)
        assert all(fm.rows >= min_rows for fm in wf.fold_models)  # the trees really split
        assert (wf.run.start, wf.run.end) == (folds[0].trade_start, END)
    assert r.a2.name == walkforward.COMBINED
    assert (r.a2.run.start, r.a2.run.end) == (folds[0].trade_start, END)
    traded = len(dates.sessions(folds[0].trade_start, folds[-1].trade_end))
    assert [p[0] for p in r.passed] == [bw.B, bw.B_LINEAR]
    assert all(0 <= p[1] <= p[2] == traded for p in r.passed)
    assert [c[0] for c in r.calibration] == [bw.B, bw.B_LINEAR]
    assert all(sum(row.rows for row in c[1]) <= r.labelled_rows for c in r.calibration)
    for curve in (r.spy_price, r.spy_tr):
        assert curve.snapshots[0].date == r.b.run.snapshots[0].date
        assert curve.snapshots[-1].date == END
    assert r.spy_tr.dividends_usd > 0
    gated_wf = r.b if r.gated == bw.B else r.b_linear
    assert r.verdict == bw.gate_p6a(
        run_metrics(gated_wf.run), curve_metrics(r.spy_tr), gated_wf.run.start, gated_wf.run.end, r.gated
    )
    assert r.frozen == strategy_b.STRATEGY_B_FROZEN


def test_execute_logs_every_step_with_its_wall_time(runs):
    logs = runs.first_logs
    for prefix in TIMED_PREFIXES:
        hits = [m for m in logs if m.startswith(prefix)]
        assert hits, prefix
        assert all(DURATION.search(m) for m in hits), prefix
    start = walkforward.folds(IS_S, FIRST_YEAR, END)[0].trade_start.isoformat()
    for prefix in (
        "1 fold(s), 2023..2023: ",
        f"{bw.B} fold 2023 ",
        f"{bw.B_LINEAR} fold 2023 ",
        f"{bw.B} {start}..{END.isoformat()}: return ",
        f"{bw.B_LINEAR} {start}..{END.isoformat()}: return ",
        f"{walkforward.COMBINED} {start}..{END.isoformat()}: return ",
        "STRATEGY_B_FROZEN at run time: ",
    ):
        assert sum(1 for m in logs if m.startswith(prefix)) == 1, prefix
    n = len(walkforward.combinations())
    assert sum(1 for m in logs if m.startswith("tune ") and f"/{n} " in m) == n
    assert sum(1 for m in logs if m.startswith(f"tune: {n} runs on ")) == 1
    assert any(m.startswith("gate ") and runs.first.verdict.sentence in m for m in logs)


def test_wall_times_reach_logs_only(runs):
    real = [float(x) for m in runs.first_logs for x in DURATION.findall(m)]
    fake = [float(x) for m in runs.second_logs for x in DURATION.findall(m)]
    assert real and len(real) == len(fake)
    assert all(x < 1000.0 for x in real)
    assert all(x >= 1000.0 for x in fake)  # the fake clocks really drove the second run's logs
    assert runs.first == runs.second
    for p1, p2 in zip(runs.paths1, runs.paths2):
        assert p1.read_bytes() == p2.read_bytes(), p1.name
        assert not DURATION.search(p1.read_text(encoding="utf-8")), p1.name


def test_a2_curve_equals_backtest_wf_combined_on_the_same_market(runs):
    wf = cmd_wf.execute(in_memory_market(), EXPECTED_ROWS, DIVIDENDS, IS_S, FIRST_YEAR, END)
    assert runs.first.a2 == wf.combined
    assert runs.first.a2.selections == wf.combined.selections
    assert runs.first.a2.run.snapshots == wf.combined.run.snapshots


# ---- run(): the artifact on a pass only ---------------------------------------------------------


@pytest.mark.parametrize("gated", [bw.B, bw.B_LINEAR])
def test_run_pass_writes_the_gated_curves_last_fold_model(
    pg, point_cli_at, tmp_path, monkeypatch, caplog, runs, gated
):
    seed(pg)
    write_dividends(tmp_path)
    report = _stand_in(runs.first, passed=True, gated=gated)
    seen, calls = _patch_run(monkeypatch, report)
    caplog.set_level(logging.INFO)

    assert cli.main(argv(tmp_path)) == 0

    assert seen == [(EXPECTED_ROWS, DIVIDENDS, IS_S, FIRST_YEAR, END)]
    assert len(calls) == 1 and calls[0][0] == tmp_path / "out" and calls[0][1] is report
    curve = runs.first.b if gated == bw.B else runs.first.b_linear
    other = runs.first.b_linear if gated == bw.B else runs.first.b
    path = tmp_path / "models" / ARTIFACT_NAME
    assert [p.name for p in (tmp_path / "models").iterdir()] == [ARTIFACT_NAME]
    data = path.read_bytes()
    assert data == b_model.dumps(curve.fold_models[-1].model)
    assert data != b_model.dumps(other.fold_models[-1].model)
    digest = hashlib.sha256(data).hexdigest()
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith(f"wrote {path} ") and digest in m for m in messages)
    freeze = [m for m in messages if "STRATEGY_B_FROZEN = FrozenModel(" in m]
    assert len(freeze) == 1
    assert digest in freeze[0]
    tune_end = curve.fold_models[-1].fold.tune_end
    assert f"train_end=date({tune_end.year}, {tune_end.month}, {tune_end.day})" in freeze[0]


def test_run_fail_writes_the_report_but_no_artifact(pg, point_cli_at, tmp_path, monkeypatch, caplog, runs):
    seed(pg)
    write_dividends(tmp_path)
    report = _stand_in(runs.first, passed=False, gated=bw.B)
    _, calls = _patch_run(monkeypatch, report)
    caplog.set_level(logging.INFO)

    assert cli.main(argv(tmp_path)) == 0

    assert len(calls) == 1
    assert not (tmp_path / "models").exists()
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("STRATEGY_B_FROZEN is None, as it stays after a failed gate") for m in messages)


def test_run_pass_with_matching_frozen_constant_logs_the_match(
    pg, point_cli_at, tmp_path, monkeypatch, caplog, runs
):
    seed(pg)
    write_dividends(tmp_path)
    fm = runs.first.b.fold_models[-1]
    artifact = tmp_path / "models" / ARTIFACT_NAME
    frozen = strategy_b.FrozenModel(
        report=cmd._repo_path(tmp_path / "out" / FILE_NAMES[0]),
        artifact=cmd._repo_path(artifact),
        train_end=fm.fold.tune_end,
        sha256=hashlib.sha256(b_model.dumps(fm.model)).hexdigest(),
    )
    report = _stand_in(runs.first, passed=True, gated=bw.B, frozen=frozen)
    _patch_run(monkeypatch, report)
    caplog.set_level(logging.INFO)

    assert cli.main(argv(tmp_path)) == 0

    assert artifact.is_file()
    assert any(r.getMessage().startswith("STRATEGY_B_FROZEN matches this run's artifact") for r in caplog.records)
    assert not any(
        r.levelno >= logging.WARNING and "STRATEGY_B_FROZEN" in r.getMessage() for r in caplog.records
    )


# ---- preconditions (exit 2, nothing written) -----------------------------------------------


def _nothing_written(tmp_path) -> bool:
    return not (tmp_path / "out").exists() and not (tmp_path / "models").exists()


def test_empty_bars_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, with_bars=False)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert _nothing_written(tmp_path)


def test_no_spy_bars_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, with_spy=False)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert _nothing_written(tmp_path)


@pytest.mark.parametrize(
    "extra",
    [
        ["--end", dates.next_session(END).isoformat()],  # after the last SPY bar
        ["--end", date(2023, 6, 10).isoformat()],  # a Saturday
        ["--first-year", "2022"],  # fold 2022 would train on nothing before is_start
        ["--first-year", "2024"],  # no fold: 2024's first session is after --end
    ],
)
def test_bad_windows_exit_2(pg, point_cli_at, tmp_path, extra):
    seed(pg)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path, *extra)) == 2
    assert _nothing_written(tmp_path)


def test_no_fx_before_is_start_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, fx_rows=((FX_LATE, "16250.5"),))
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert _nothing_written(tmp_path)


def test_missing_dividends_file_exits_2(pg, point_cli_at, tmp_path):
    seed(pg)
    assert cli.main(argv(tmp_path)) == 2  # no spy_dividends.csv written
    assert _nothing_written(tmp_path)


# ---- end to end ------------------------------------------------------------------------------


def test_end_to_end_cli_run_is_read_only_and_writes_the_report_set(pg, point_cli_at, tmp_path, caplog):
    seed(pg)
    write_dividends(tmp_path)
    caplog.set_level(logging.INFO)
    before = checksums(pg)

    assert cli.main(argv(tmp_path)) == 0

    assert checksums(pg) == before  # read-only
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == sorted(FILE_NAMES)
    assert [p.name for p in (tmp_path / "cache").iterdir()] == [f"bars-{END.isoformat()}-{EXPECTED_ROWS}.pkl"]
    md = (tmp_path / "out" / FILE_NAMES[0]).read_text(encoding="utf-8")
    gate = b_report.parse_machine_line(md, b_report.GATE_KEY)
    assert gate in ("passed", "failed")
    artifact = tmp_path / "models" / ARTIFACT_NAME
    assert artifact.is_file() == (gate == "passed")
    assert (tmp_path / "models").exists() == (gate == "passed")
    messages = [r.getMessage() for r in caplog.records]
    assert sum(1 for m in messages if m.startswith("wrote ")) == len(FILE_NAMES) + (1 if gate == "passed" else 0)
    assert any(m.startswith("execute: done ") for m in messages)
