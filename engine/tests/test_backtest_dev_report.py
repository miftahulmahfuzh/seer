"""Dev report and pre-registration renderers (phase 10; handover §7.6, §7.7, §7.8): every §7.6
section, byte stability, no run date in content, the D8 sentences, the none-eligible files, the
CSVs, the frontier SVG and the report checks, all from fake DevRows on a small synthetic window.
The DevReport is built here the way phase 12's command builds it."""

from __future__ import annotations

import csv
import dataclasses
import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from seer_engine import dates
from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.book_runner import RunStats
from seer_engine.backtest.dev import DEV_END, FAILURE_LABELS, Candidate, DevRow, finalists
from seer_engine.backtest.dev_report import (
    ROWS_CSV_HEADER,
    TEST_SLICE_START,
    TEST_START,
    DevReport,
    _month_end_points,
    _top_by_mar,
    curves_csv,
    frontier_svg,
    preregistration_name,
    render_markdown,
    render_preregistration,
    report_stem,
    rows_csv,
)
from seer_engine.backtest.metrics import Metrics
from seer_engine.backtest.runner import YearGap
from seer_engine.sim import Snapshot
from seer_engine.sim.rules import DAILY_SWITCH, DESIGN_V0, MONTHLY_HOLD, SWING_T20, describe_rules

D = date.fromisoformat
RUN_DATE = D("2026-10-20")
ADDED = D("2026-10-06")
SPY_START = D("2014-01-02")
LATE_START = D("2014-06-02")
FINGERPRINT = "f" * 64
DIGEST = "d" * 64
COUNTS = {"bar_rows": 1234567, "symbols_requested": 900, "symbols_served": 812, "dividend_rows": 40000, "fx_rows": 4300}
UNSERVED = ("ZZA", "ABK", "MMM1")


@dataclass(frozen=True)
class FakeParams:
    hold: str
    n: int = 20

    def as_dict(self) -> dict[str, str]:
        return {"hold": self.hold, "n": str(self.n)}


class FakeEtf:
    """An Allocator holding one fixed ETF (structurally satisfies strategies.allocator.Allocator)."""

    id = "FAKE"

    def lookback(self, params):
        return params.n

    def symbols(self, params):
        return tuple(sorted({params.hold, "SPY"}))

    def holds(self, params):
        return (params.hold,)

    def uses_members(self, params):
        return False

    def targets(self, history, members, data_date, held, params):
        return ()

    def prepare(self, history):
        return None

    def targets_prepared(self, prepared, members, data_date, held, params):
        return ()


class FakeMembers(FakeEtf):
    id = "FAKEM"

    def symbols(self, params):
        return ("SPY",)

    def holds(self, params):
        return ()

    def uses_members(self, params):
        return True


ETF = FakeEtf()
MEMBERS = FakeMembers()

# id, family, rules, allocator, hold, start, return, cagr, max dd, pf, trades, failed, owner inputs
SPECS = (
    ("F1-A", "F1", MONTHLY_HOLD, ETF, "SPY", SPY_START, 0.30, 0.12, 0.10, 1.6, 140, (), ()),
    ("F1-B", "F1", DAILY_SWITCH, ETF, "QQQ", LATE_START, 0.35, 0.13, 0.12, 1.5, 150, (), ()),
    ("F2-A", "F2", MONTHLY_HOLD, ETF, "IEF", LATE_START, 0.28, 0.11, 0.11, 1.4, 120, ("owner inputs",), ("etf:IEF",)),
    ("F4-A", "F4", MONTHLY_HOLD, MEMBERS, "SPY", LATE_START, 0.40, 0.15, 0.14, 1.35, 200, (), ()),
    (
        "F7-A",
        "F7",
        SWING_T20,
        MEMBERS,
        "SPY",
        LATE_START,
        0.05,
        0.02,
        0.25,
        1.1,
        300,
        ("beats SPY TR", FAILURE_LABELS[1], "PF >= 1.3"),
        (),
    ),
    ("F3-A", "F3", MONTHLY_HOLD, ETF, "SPY", SPY_START, 0.26, 0.10, 0.08, 2.0, 40, (">= 100 trades",), ()),
    (
        "REF-Z",
        "REF",
        MONTHLY_HOLD,
        ETF,
        "SPY",
        SPY_START,
        0.0,
        None,
        0.0,
        None,
        0,
        ("beats SPY TR", "PF >= 1.3", ">= 100 trades"),
        (),
    ),
)
IDS = tuple(s[0] for s in SPECS)


def _equity(i: int, k: int) -> Decimal:
    return Decimal(10000 + i * (k + 1) + (i % (k + 3)) * 5).quantize(Decimal("0.0001"))


def _snapshots(start: date, k: int) -> tuple[Snapshot, ...]:
    days = [dates.prev_session(start), *dates.sessions(start, DEV_END)]
    return tuple(Snapshot(d, _equity(i, k), _equity(i, k)) for i, d in enumerate(days))


def _run(spec, k: int, *, all_fail: bool = False) -> tuple[tuple[Snapshot, ...], DevRow]:
    cid, family, rules, alloc, hold, start, ret, cagr, dd, pf, trades, failed, owner = spec
    if all_fail and not failed:
        failed = ("beats SPY TR",)
    cand = Candidate(
        id=cid,
        family=family,
        rules=rules,
        allocator=alloc,
        params=FakeParams(hold=hold),
        rationale=f"Rationale for {cid}, with a comma",
        added=ADDED,
        owner_inputs=owner,
    )
    stats = RunStats(
        metrics=Metrics(
            total_return=ret,
            win_rate=0.5,
            profit_factor=pf,
            max_drawdown=dd,
            trades=trades,
            months=20.0,
            cagr=cagr,
        ),
        exposure=0.5 + k / 100,
        turnover=2.0 + k,
        costs_usd=10.0 + k,
        gross_pnl_usd=100.0,
        cost_drag=(10.0 + k) / 100.0,
        dividends_usd=5.0,
        sharpe=0.25 * k - 0.5,
        daily_returns=(0.001 * k, -0.002, 0.003),
        year_returns=((2014, ret / 2), (2015, ret / 3)),
        worst_year=(2015, ret / 3),
    )
    spy_tr = Metrics(total_return=0.25, win_rate=None, profit_factor=None, max_drawdown=0.12, trades=0, months=20.0, cagr=0.1)
    spy_price = Metrics(total_return=0.22, win_rate=None, profit_factor=None, max_drawdown=0.13, trades=0, months=20.0, cagr=0.09)
    row = DevRow(
        candidate=cand,
        start=start,
        end=DEV_END,
        stats=stats,
        spy_tr=spy_tr,
        spy_price=spy_price,
        beats_spy="beats SPY TR" not in failed,  # phase 9 checks it agrees with failed
        mar=None if cagr is None or dd == 0 else cagr / dd,
        eligible=not failed,
        failed=tuple(failed),
    )
    return _snapshots(start, k), row


def _spy(name: str, k: int) -> BenchmarkCurve:
    return BenchmarkCurve(
        name=name, snapshots=_snapshots(SPY_START, k), shares=10, cash=Decimal("1.0000"), dividends_usd=Decimal("12.3400")
    )


def _top_years(rows, finals, k=5):
    """Phase 12's rule: the finalists first, then the remaining rows by (-MAR, id), up to k."""
    chosen = [r.candidate.id for r in finals][:k]
    for r in sorted((r for r in rows if r.mar is not None), key=lambda r: (-r.mar, r.candidate.id)):
        if len(chosen) >= k:
            break
        if r.candidate.id not in chosen:
            chosen.append(r.candidate.id)
    by_id = {r.candidate.id: r for r in rows}
    return tuple((cid, tuple(by_id[cid].stats.year_returns)) for cid in chosen)


def _report(*, all_fail: bool = False, run_date: date = RUN_DATE) -> DevReport:
    runs = [_run(s, k, all_fail=all_fail) for k, s in enumerate(SPECS)]
    rows = tuple(row for _, row in runs)
    finals = finalists(rows)
    if finals:
        dsr = tuple((f.candidate.id, 0.5 + i / 10) for i, f in enumerate(finals))
    else:
        best = min(rows, key=lambda r: (-r.stats.sharpe, r.candidate.id))
        dsr = ((best.candidate.id, 0.123),)
    return DevReport(
        run_date=run_date,
        store_fingerprint=FINGERPRINT,
        store_counts=COUNTS,
        unserved=tuple(sorted(UNSERVED)),
        survivorship=(YearGap(2014, 1000, 50, 30, 20), YearGap(2015, 800, 40, 25, 15)),
        registry_digest=DIGEST,
        rows=rows,
        finalists=finals,
        spy_window=(SPY_START, DEV_END),
        spy_price=_spy("SPY price-only", 1),
        spy_tr=_spy("SPY total-return", 2),
        top_years=_top_years(rows, finals),
        curves=tuple((row.candidate.id, _month_end_points(snaps)) for snaps, row in runs),
        dsr=dsr,
    )


def _section(md: str, heading: str) -> str:
    start = md.index(f"\n## {heading}\n")
    end = md.find("\n## ", start + 1)
    return md[start : end if end != -1 else len(md)]


# --------------------------------------------------------------------------- names and windows


def test_report_stem_and_preregistration_name():
    assert report_stem(RUN_DATE) == "2026-10-20-p7a-dev-exploration"
    assert preregistration_name(RUN_DATE) == "2026-10-20-p7b-preregistration.md"
    with pytest.raises(TypeError):
        report_stem("2026-10-20")


def test_test_window_starts_the_session_after_dev_end():
    assert TEST_START == dates.next_session(DEV_END)
    assert dates.is_session(TEST_SLICE_START)


# --------------------------------------------------------------------------- helpers


def test_the_fixture_matches_d8():
    r = _report()
    assert [f.candidate.id for f in r.finalists] == ["F1-A", "F4-A"]  # F1-B loses to F1-A (one per family)
    assert [cid for cid, _ in r.top_years] == ["F1-A", "F4-A", "F3-A", "F1-B", "F2-A"]
    assert _report(all_fail=True).finalists == ()


def test_top_by_mar_skips_rows_without_mar_and_breaks_ties_by_id():
    r = _report()
    rows = [dataclasses.replace(row, mar=1.0) if row.candidate.id in ("F2-A", "F1-B") else row for row in r.rows]
    assert [row.candidate.id for row in _top_by_mar(rows, 10)] == ["F3-A", "F1-A", "F4-A", "F1-B", "F2-A", "F7-A"]


def test_month_end_points_keeps_the_last_snapshot_of_each_month():
    snaps = [
        Snapshot(D("2015-08-28"), Decimal("100"), Decimal("100")),
        Snapshot(D("2015-08-31"), Decimal("110"), Decimal("110")),
        Snapshot(D("2015-09-01"), Decimal("90"), Decimal("90")),
        Snapshot(D("2015-09-30"), Decimal("120"), Decimal("120")),
        Snapshot(D("2015-10-01"), Decimal("130"), Decimal("130")),
    ]
    assert _month_end_points(snaps) == ((D("2015-08-31"), 1.1), (D("2015-09-30"), 1.2), (D("2015-10-01"), 1.3))
    with pytest.raises(ValueError):
        _month_end_points([])


# --------------------------------------------------------------------------- validation


def _bad_reports():
    r = _report()
    # Phase 9's DevRow already refuses a late end at construction; force one past it so the
    # renderer's own D9 check (the third guard) is what this case exercises.
    late_row = dataclasses.replace(r.rows[0])
    object.__setattr__(late_row, "end", D("2015-10-19"))
    return [
        ("after-dev-end", dataclasses.replace(r, rows=(late_row, *r.rows[1:]))),
        ("finalist-not-eligible", dataclasses.replace(r, finalists=(r.rows[4],))),
        ("duplicate-ids", dataclasses.replace(r, rows=(*r.rows, r.rows[0]))),
        ("curves-mismatch", dataclasses.replace(r, curves=r.curves[1:])),
        ("spy-window", dataclasses.replace(r, spy_window=(D("2014-01-03"), DEV_END))),
        ("store-counts", dataclasses.replace(r, store_counts={"bar_rows": 1})),
        ("unsorted-unserved", dataclasses.replace(r, unserved=("ZZA", "ABK"))),
        ("dsr-not-finalists", dataclasses.replace(r, dsr=(("F1-B", 0.5),))),
        ("top-years-unknown", dataclasses.replace(r, top_years=(("NOPE", ()),))),
        ("too-many-finalists", dataclasses.replace(r, finalists=(r.rows[0], r.rows[1], r.rows[3], r.rows[0]))),
    ]


@pytest.mark.parametrize("name,report", _bad_reports(), ids=[n for n, _ in _bad_reports()])
def test_every_renderer_rejects_an_invalid_report(name, report):
    for render in (render_markdown, rows_csv, curves_csv, frontier_svg, render_preregistration):
        with pytest.raises(ValueError):
            render(report)


def test_params_without_as_dict_is_a_type_error():
    r = _report()
    row = r.rows[0]
    bare = dataclasses.replace(row, candidate=dataclasses.replace(row.candidate, params=object()))
    with pytest.raises(TypeError, match="as_dict"):
        render_markdown(dataclasses.replace(r, rows=(bare, *r.rows[1:]), finalists=(), dsr=()))


@dataclass(frozen=True)
class FakePart:
    allocator: object
    params: object
    share: Decimal


@dataclass(frozen=True)
class FakeBlend:
    parts: tuple
    note: str | None = None
    on: bool = True


class FakeBlendAllocator(FakeEtf):
    id = "BLEND"

    def symbols(self, params):
        return ("QQQ", "SPY")

    def holds(self, params):
        return ("SPY",)

    def uses_members(self, params):
        return True


def test_params_without_as_dict_render_by_dataclass_fields():
    r = _report()
    row = r.rows[0]
    blend = FakeBlend(parts=(FakePart(ETF, FakeParams("SPY", 200), Decimal("0.7")), FakePart(MEMBERS, FakeParams("QQQ"), Decimal("0.3"))))
    cand = dataclasses.replace(row.candidate, allocator=FakeBlendAllocator(), params=blend)
    rows = (dataclasses.replace(row, candidate=cand), *r.rows[1:])
    text = render_preregistration(dataclasses.replace(r, rows=rows, finalists=(rows[0], r.finalists[1])))
    assert (
        '{"parts": [{"allocator": "<FAKE>", "params": {"hold": "SPY", "n": "200"}, "share": "0.7"}, '
        '{"allocator": "<FAKEM>", "params": {"hold": "QQQ", "n": "20"}, "share": "0.3"}], "note": null, "on": "true"}'
    ) in render_markdown(dataclasses.replace(r, rows=rows, finalists=(rows[0], r.finalists[1])))
    assert '"allocator": "<FAKE>"' in text


# --------------------------------------------------------------------------- markdown


def test_every_renderer_is_byte_stable():
    a, b = _report(), _report()
    for render in (render_markdown, rows_csv, curves_csv, frontier_svg, render_preregistration):
        first = render(a)
        assert first == render(b)
        assert first.endswith("\n") and not first.endswith("\n\n")


def test_no_run_date_in_content_outside_file_names():
    r = _report()
    other = _report(run_date=D("2026-10-21"))
    for render in (render_markdown, rows_csv, curves_csv, frontier_svg, render_preregistration):
        text = render(r).replace(report_stem(RUN_DATE), "<stem>")
        assert RUN_DATE.isoformat() not in text
        assert text == render(other).replace(report_stem(D("2026-10-21")), "<stem>")


def test_markdown_has_every_section_in_order():
    md = render_markdown(_report())
    headings = [line[3:] for line in md.splitlines() if line.startswith("## ")]
    assert headings == [
        "Data",
        "Method",
        "Candidates",
        "Results",
        "Frontier",
        "SPY on the development window",
        "Year by year, top 5",
        "Survivorship bias",
        "Multiple testing",
        "Finalists (D8)",
        "Plain statements",
    ]


def test_markdown_data_and_method_facts():
    md = render_markdown(_report())
    data = _section(md, "Data")
    assert f"`{FINGERPRINT}`" in data
    assert "- Bar rows: 1,234,567" in data and "- USD/IDR rows: 4,300" in data
    method = _section(md, "Method")
    assert f"`{DIGEST}`" in method
    assert "Trials: 7." in method
    for marker in ("**D1, split.**", "**D3, windows.**", "**D6, registry.**", "**D7, every try reported.**", "**D8, finalists.**", "**D9, test window untouched.**"):
        assert marker in method
    for rules in (MONTHLY_HOLD, DAILY_SWITCH, SWING_T20):
        assert f"- `{rules.id}`, used by" in method
        for text in describe_rules(rules):
            assert f"  - {text}" in method


def test_markdown_has_one_results_row_per_candidate():
    md = render_markdown(_report())
    results = _section(md, "Results")
    for cid in IDS:
        assert sum(1 for line in results.splitlines() if line.startswith(f"| `{cid}` |")) == 1
    f1a = next(line for line in results.splitlines() if line.startswith("| `F1-A` |"))
    assert "| +30.0% |" in f1a and "| 10.0% |" in f1a and "| 1.60 |" in f1a and "| 140 |" in f1a
    assert "| +25.0% |" in f1a and "| finalist |" in f1a
    f2a = next(line for line in results.splitlines() if line.startswith("| `F2-A` |"))
    assert "fail: owner inputs" in f2a and "etf:IEF" in f2a
    f1b = next(line for line in results.splitlines() if line.startswith("| `F1-B` |"))
    assert "| eligible |" in f1b
    assert "-rows.csv" in results


def test_markdown_spy_years_survivorship_and_frontier_link():
    r = _report()
    md = render_markdown(r)
    stem = report_stem(RUN_DATE)
    assert f"]({stem}-frontier.svg)" in _section(md, "Frontier")
    spy = _section(md, "SPY on the development window")
    assert "| SPY price-only |" in spy and "| SPY total-return |" in spy and f"]({stem}-curves.csv)" in spy
    years = _section(md, "Year by year, top 5")
    assert "| Year | `F1-A` | `F4-A` | `F3-A` | `F1-B` | `F2-A` | SPY TR |" in years
    assert "| 2014 | +15.0% | +20.0% | +13.0% | +17.5% | +14.0% |" in years
    surv = _section(md, "Survivorship bias")
    assert "optimistic" in surv and "ticker reuse" in surv
    assert "| All | 1,800 | 90 | 55 | 35 | 5.00% |" in surv
    assert "`F4-A`, `F7-A`" in surv
    assert "ABK, MMM1, ZZA." in surv


def test_markdown_multiple_testing_and_d8_sentences():
    md = render_markdown(_report())
    mt = _section(md, "Multiple testing")
    assert "Trials: 7 candidates" in mt and "Deflated Sharpe" in mt
    assert "| `F1-A` | -0.50 | 0.500 |" in mt and "| `F4-A` | 0.25 | 0.600 |" in mt
    fin = _section(md, "Finalists (D8)")
    assert "1. `F1-A` (F1, rules `monthly-hold`) is eligible:" in fin
    assert "2. `F4-A` (F4, rules `monthly-hold`) is eligible:" in fin
    assert "ranks 1 of 3 eligible" in fin and "ranks 3 of 3 eligible" in fin
    assert "- `F1-B`: family F1 already has `F1-A`." in fin
    assert "| >= 100 trades | 2 |" in fin


def test_markdown_plain_statements():
    md = render_markdown(_report())
    plain = _section(md, "Plain statements")
    assert "excludes low-turnover designs by construction" in plain
    assert "Candidates that failed on the trade count alone: 1." in plain
    assert "FX before 1999-01-04 only affects starting capital" in plain
    assert "2026-11-01" in plain and "February 2027" in plain and "into SPY directly" in plain


def test_markdown_none_eligible():
    r = _report(all_fail=True)
    md = render_markdown(r)
    assert "none of the 7 candidates is eligible" in md
    fin = _section(md, "Finalists (D8)")
    assert "**None eligible.**" in fin and "P7b does not run" in fin
    assert "No finalist; shown for the candidate with the highest Sharpe ratio:" in md


# --------------------------------------------------------------------------- CSV and SVG


def test_rows_csv():
    text = rows_csv(_report())
    rows = list(csv.reader(io.StringIO(text)))
    assert ",".join(rows[0]) == ROWS_CSV_HEADER
    assert [row[0] for row in rows[1:]] == list(IDS)
    by_id = {row[0]: dict(zip(rows[0], row)) for row in rows[1:]}
    assert by_id["F1-A"]["total_return"] == "0.300000"
    assert by_id["F1-A"]["finalist"] == "true" and by_id["F1-B"]["finalist"] == "false"
    assert by_id["F1-B"]["eligible"] == "true"
    assert by_id["F2-A"]["owner_inputs"] == "etf:IEF" and by_id["F2-A"]["failed"] == "owner inputs"
    assert by_id["REF-Z"]["cagr"] == "" and by_id["REF-Z"]["profit_factor"] == "" and by_id["REF-Z"]["mar"] == ""
    assert by_id["F7-A"]["failed"] == f"beats SPY TR;{FAILURE_LABELS[1]};PF >= 1.3"
    assert by_id["F1-A"]["worst_year"] == "2015"
    assert by_id["F1-A"]["spy_tr_total_return"] == "0.250000" and by_id["F1-A"]["spy_tr_cagr"] == "0.100000"


def test_curves_csv():
    text = curves_csv(_report())
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["date", *IDS, "spy_price", "spy_tr"]
    first = dict(zip(rows[0], rows[1]))
    assert first["date"] == "2013-12-31"
    assert first["F1-A"] == "1.000000" and first["spy_tr"] == "1.000000" and first["F1-B"] == ""
    may = dict(zip(rows[0], next(r for r in rows if r[0] == "2014-05-30")))
    assert may["F1-B"] == "1.000000"
    assert rows[-1][0] == DEV_END.isoformat()
    assert [r[0] for r in rows[1:]] == sorted(r[0] for r in rows[1:])


def test_frontier_svg():
    r = _report()
    svg = frontier_svg(r)
    root = ET.fromstring(svg.encode("utf-8"))
    ns = "{http://www.w3.org/2000/svg}"
    dots = [c for c in root.iter(f"{ns}circle") if c.find(f"{ns}title") is not None]
    assert len(dots) == 6  # REF-Z has no CAGR
    classes = sorted(c.get("class") for c in dots)
    assert classes == ["el", "fi", "fi", "pt", "pt", "pt"]
    texts = [t.text for t in root.iter(f"{ns}text")]
    assert "F1-A" in texts and "F4-A" in texts and "F1-B" not in texts
    assert "SPY total-return" in texts
    assert any(t and t.startswith("max drawdown 20%") for t in texts)
    assert "Not plotted (no CAGR or drawdown): 1." in svg
    assert root.find(f"{ns}line[@class='lim']") is not None


def test_frontier_handles_negative_cagr():
    r = _report()
    row = r.rows[4]
    neg = dataclasses.replace(row, stats=dataclasses.replace(row.stats, metrics=dataclasses.replace(row.stats.metrics, cagr=-0.07)))
    svg = frontier_svg(dataclasses.replace(r, rows=(*r.rows[:4], neg, *r.rows[5:])))
    assert ">-10%<" in svg or ">-8%<" in svg or ">-7.5%<" in svg


# --------------------------------------------------------------------------- pre-registration


def test_preregistration_names_each_finalist_exactly():
    r = _report()
    text = render_preregistration(r)
    stem = report_stem(RUN_DATE)
    assert text.startswith("# P7b pre-registration\n")
    assert f"(../backtests/{stem}.md)" in text and f"`{DIGEST}`" in text and f"`{FINGERPRINT}`" in text
    assert "### 1. `F1-A`" in text and "### 2. `F4-A`" in text
    assert "`F1-B`" not in text.split("## Finalists")[1].split("## Test window")[0]
    assert '{\n  "hold": "SPY",\n  "n": "20"\n}' in text
    assert (
        "TradeRules(id='monthly-hold', engine='book', cadence='monthly', resize_cadence=None, "
        "entry='open_limit', max_positions=None, "
        "time_stop=None, resize=True, fractional=False, dividends=True, idle_symbol=None, cost_rate=Decimal('0.001'), "
        "cost_model='flat')"
    ) in text
    assert "| cost_rate | 0.001 |" in text and "| idle_symbol | none |" in text
    assert "- Instruments held: SPY" in text
    assert "- Instruments held: S&P 500 ∪ Nasdaq-100 members (point in time)" in text
    assert "- Instruments read: SPY + S&P 500 ∪ Nasdaq-100 members (point in time)" in text
    assert "- Owner inputs: none" in text
    assert f"- Main: {TEST_START.isoformat()} → data end" in text
    assert f"{TEST_SLICE_START.isoformat()} → data end" in text
    assert "- Max drawdown ≤ 20%." in text and "- Profit factor ≥ 1.3." in text and "- ≥ 100 closed trades." in text
    assert "Beats total-return SPY" in text
    revision = text.split("## Proposed design-§5 revision (D10)")[1]
    for line in describe_rules(DESIGN_V0):
        assert f"- {line}" in revision
    assert "### Rule set `monthly-hold` (used by `F1-A`, `F4-A`)" in revision
    for line in describe_rules(MONTHLY_HOLD):
        assert f"- {line}" in revision
    assert "optimistic" in text and "2026-11-01" in text and "February 2027" in text


def test_preregistration_none_eligible():
    r = _report(all_fail=True)
    text = render_preregistration(r)
    stem = report_stem(RUN_DATE)
    assert "## None eligible" in text and "**P7b does not run**" in text
    assert f"(../backtests/{stem}-frontier.svg)" in text
    assert "## Finalists" not in text and "## Proposed design-§5 revision" not in text
    assert "| `F3-A` | F3 |" in text
    assert "2026-11-01" in text and "optimistic" in text
