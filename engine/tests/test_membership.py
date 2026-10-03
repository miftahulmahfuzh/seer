"""Phase 2: point-in-time membership (engine/src/seer_engine/membership.py, commands/universe.py)."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pytest

from seer_engine import membership as m
from seer_engine.commands import universe as cmd
from seer_engine.membership import Alias, Interval, MembershipError, Override

D = date.fromisoformat


def snaps(*rows: tuple[str, str]) -> list[m.Snapshot]:
    return [(D(d), frozenset(t.split(","))) for d, t in rows]


def write(path: Path, text: str) -> Path:
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return path


# --- loading -----------------------------------------------------------------------------


def test_load_snapshots_reads_quoted_list_and_dot_form(tmp_path):
    path = write(
        tmp_path / "x.csv",
        'date,tickers\n2020-01-02,"AAPL,BRK.B,MSFT"\n2020-03-02,"AAPL,BRK-B"\n',
    )
    assert m.load_snapshots(path) == [
        (D("2020-01-02"), frozenset({"AAPL", "BRK.B", "MSFT"})),
        (D("2020-03-02"), frozenset({"AAPL", "BRK.B"})),
    ]


def test_load_snapshots_rejects_unsorted_dates(tmp_path):
    path = write(tmp_path / "x.csv", 'date,tickers\n2020-03-02,"A"\n2020-01-02,"A"\n')
    with pytest.raises(MembershipError, match="ascending"):
        m.load_snapshots(path)


def test_normalize_ticker():
    assert m.normalize_ticker(" brk-b ") == "BRK.B"
    assert m.normalize_ticker("BF.B") == "BF.B"
    with pytest.raises(MembershipError):
        m.normalize_ticker("Apple Inc.")


# --- intervals ---------------------------------------------------------------------------


def test_build_intervals_exclusive_end_and_open_interval():
    s = snaps(("2020-01-02", "A,B"), ("2020-02-03", "A,C"))
    assert m.build_intervals(s, "SP500") == [
        Interval("A", "SP500", D("2020-01-02"), None, "A"),
        Interval("B", "SP500", D("2020-01-02"), D("2020-02-03"), "B"),
        Interval("C", "SP500", D("2020-02-03"), None, "C"),
    ]


def test_build_intervals_leave_and_rejoin_gives_two_intervals():
    s = snaps(("2020-01-02", "A,B"), ("2020-02-03", "A"), ("2020-05-01", "A,B"))
    got = [iv for iv in m.build_intervals(s, "NDX") if iv.symbol == "B"]
    assert got == [
        Interval("B", "NDX", D("2020-01-02"), D("2020-02-03"), "B"),
        Interval("B", "NDX", D("2020-05-01"), None, "B"),
    ]


def test_alias_merges_contiguous_rename_into_one_interval():
    s = snaps(("2012-12-12", "AAPL,FB"), ("2022-06-09", "AAPL,META"))
    aliases = [Alias("FB", "META", D("2022-06-09"), "")]
    got = [iv for iv in m.build_intervals(s, "NDX", aliases) if iv.symbol == "META"]
    assert got == [Interval("META", "NDX", D("2012-12-12"), None, "FB/META")]


def test_alias_does_not_apply_on_or_after_effective_date():
    # The old ticker re-used by a different company after the rename stays itself.
    s = snaps(("2019-01-02", "ARNC"), ("2020-04-06", "HWM"), ("2021-01-04", "ARNC,HWM"))
    aliases = [Alias("ARNC", "HWM", D("2020-04-06"), "")]
    got = m.build_intervals(s, "SP500", aliases)
    assert got == [
        Interval("ARNC", "SP500", D("2021-01-04"), None, "ARNC"),
        Interval("HWM", "SP500", D("2019-01-02"), None, "ARNC/HWM"),
    ]


def test_alias_collision_in_one_snapshot_is_an_error():
    s = snaps(("2020-01-02", "FB,META"),)
    with pytest.raises(MembershipError, match="both resolve to META"):
        m.build_intervals(s, "NDX", [Alias("FB", "META", D("2022-06-09"), "")])


def test_load_aliases_rejects_chains(tmp_path):
    path = write(
        tmp_path / "a.csv",
        "old,new,effective_date,note\nHCP,PEAK,2019-11-05,\nPEAK,DOC,2024-03-01,\n",
    )
    with pytest.raises(MembershipError, match="chain"):
        m.load_aliases(path)


# --- overrides ---------------------------------------------------------------------------


def test_overrides_after_last_snapshot_append_snapshots():
    s = snaps(("2026-05-18", "A,B,C"))
    overrides = [
        Override(D("2026-06-22"), "NDX", "add", "D", ""),
        Override(D("2026-06-22"), "NDX", "remove", "B", ""),
        Override(D("2026-08-04"), "NDX", "remove", "C", ""),
        Override(D("2026-09-21"), "SP500", "add", "Z", ""),  # other index: ignored
    ]
    got = m.apply_overrides(s, overrides, "NDX")
    assert got == [
        (D("2026-05-18"), frozenset({"A", "B", "C"})),
        (D("2026-06-22"), frozenset({"A", "C", "D"})),
        (D("2026-08-04"), frozenset({"A", "D"})),
    ]
    ivs = {iv.symbol: iv for iv in m.build_intervals(got, "NDX")}
    assert ivs["B"].end_date == D("2026-06-22")
    assert ivs["C"].end_date == D("2026-08-04")
    assert ivs["D"] == Interval("D", "NDX", D("2026-06-22"), None, "D")


@pytest.mark.parametrize("when", ["2026-05-18", "2026-01-02"])
def test_override_on_or_before_last_snapshot_is_rejected(when):
    s = snaps(("2026-05-18", "A,B"))
    with pytest.raises(MembershipError, match="not after"):
        m.apply_overrides(s, [Override(D(when), "NDX", "add", "C", "")], "NDX")


def test_override_removing_non_member_is_rejected():
    s = snaps(("2026-05-18", "A,B"))
    with pytest.raises(MembershipError, match="not a member"):
        m.apply_overrides(s, [Override(D("2026-06-01"), "NDX", "remove", "Q", "")], "NDX")


def test_load_overrides_rejects_bad_action(tmp_path):
    path = write(
        tmp_path / "o.csv",
        "date,index_id,action,ticker,note\n2026-06-22,NDX,swap,A,\n",
    )
    with pytest.raises(MembershipError, match="add\\|remove"):
        m.load_overrides(path)


# --- vendored data -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def vendored() -> list[Interval]:
    return m.compute_universe(m.DATA_DIR)


def test_vendored_data_builds(vendored):
    sp = m.current_members(vendored, "SP500")
    ndx = m.current_members(vendored, "NDX")
    assert 495 <= len(sp) <= 510
    assert 98 <= len(ndx) <= 110
    assert "BRK.B" in sp
    assert all(iv.end_date is None or iv.start_date < iv.end_date for iv in vendored)
    assert len(m.symbols_since(vendored, D("2015-01-01"))) > 700


def test_vendored_overrides_are_applied(vendored):
    ndx = m.current_members(vendored, "NDX")
    sp = m.current_members(vendored, "SP500")
    assert {"ALAB", "CRWV", "NBIS", "RKLB", "TER", "HONA", "SPCX"} <= ndx
    assert not {"CHTR", "CTSH", "INSM", "VRSK", "ZS", "EA", "KHC"} & ndx
    assert {"BE", "P", "ILMN"} <= sp
    assert not {"TAP", "TTD", "BLDR"} & sp


def test_vendored_fb_meta_is_one_interval(vendored):
    meta = [iv for iv in vendored if iv.symbol == "META"]
    assert {iv.index_id for iv in meta} == {"SP500", "NDX"}
    assert all(iv.end_date is None and iv.source_symbol == "FB/META" for iv in meta)
    assert not [iv for iv in vendored if iv.symbol == "FB"]


def test_vendored_aliases_check_out():
    """Every alias: the old ticker is a member somewhere before its effective date, and never
    shares a snapshot with the new ticker (which would mean two different securities)."""
    aliases = m.load_aliases(m.DATA_DIR / m.ALIASES_FILE)
    all_snaps = [
        s for f in m.SNAPSHOT_FILES.values() for s in m.load_snapshots(m.DATA_DIR / f)
    ]
    for a in aliases:
        before = [d for d, t in all_snaps if a.old in t and d < a.effective_date]
        assert before, f"{a.old}->{a.new}: {a.old} never a member before {a.effective_date}"
        both = [d for d, t in all_snaps if a.old in t and a.new in t]
        assert not both, f"{a.old}->{a.new}: both in the snapshot of {both[0]}"


# --- universe check ----------------------------------------------------------------------

SP_WIKITEXT = """
{| class="wikitable sortable mw-collapsible sticky-header" id="constituents"
|-
![[Ticker symbol|Symbol]]
! Security !! GICS Sector
|-
|| {{NyseSymbol|MMM}}
|| [[3M]]
|| Industrials
|-
|| {{NyseSymbol|BRK.B}}<ref>note</ref>
|| [[Berkshire Hathaway]]
|| Financials
|}
"""

NDX_WIKITEXT = """
{| class="wikitable sortable" id="constituents"
|-
! Ticker !! Company !! ICB Industry
|-
| ADBE || [[Adobe Inc.]] || Technology
|-
| [[Alphabet Inc.|GOOGL]] || [[Alphabet Inc.]] (Class A) || Technology
|}
"""


def test_parse_constituents_both_layouts():
    assert m.parse_constituents(SP_WIKITEXT) == {"MMM", "BRK.B"}
    assert m.parse_constituents(NDX_WIKITEXT) == {"ADBE", "GOOGL"}


def test_parse_constituents_without_table_raises():
    with pytest.raises(MembershipError, match="constituents"):
        m.parse_constituents("no table here")


def _fake_fetch(pages: dict[str, str]):
    def fetch(page: str) -> str:
        return pages[page]

    return fetch


def _intervals(sp: str, ndx: str) -> list[Interval]:
    return [Interval(t, "SP500", D("2020-01-02"), None, t) for t in sp.split(",")] + [
        Interval(t, "NDX", D("2020-01-02"), None, t) for t in ndx.split(",")
    ]


def test_check_identical_exits_0():
    fetch = _fake_fetch(
        {"List of S&P 500 companies": SP_WIKITEXT, "List of NASDAQ-100 companies": NDX_WIKITEXT}
    )
    out = io.StringIO()
    assert cmd.check(_intervals("MMM,BRK.B", "ADBE,GOOGL"), fetch, out) == 0
    assert "DIFFERENT" not in out.getvalue()


def test_check_difference_exits_1_and_names_symbols():
    fetch = _fake_fetch(
        {"List of S&P 500 companies": SP_WIKITEXT, "List of NASDAQ-100 companies": NDX_WIKITEXT}
    )
    out = io.StringIO()
    ivs = _intervals("MMM,TAP", "ADBE,GOOGL") + [
        Interval("BRK.B", "SP500", D("2010-02-16"), D("2020-01-02"), "BRK.B")  # closed
    ]
    assert cmd.check(ivs, fetch, out) == 1
    text = out.getvalue()
    assert "SP500: computed 2, Wikipedia 2 -- DIFFERENT" in text
    assert "on Wikipedia, not computed: BRK.B" in text
    assert "computed, not on Wikipedia: TAP" in text
    assert "NDX: computed 2, Wikipedia 2 -- identical" in text


# --- universe refresh (DB) ---------------------------------------------------------------


def _table(conn) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT symbol, index_id, start_date, end_date, source_symbol FROM universe "
            "ORDER BY index_id, symbol, start_date"
        )
        return cur.fetchall()


def test_refresh_twice_changes_nothing(pg, vendored):
    first = cmd.refresh(pg, vendored, dry_run=False)
    assert first.changed and first.rows == len(vendored)
    snapshot = _table(pg)
    assert len(snapshot) == len(vendored)

    second = cmd.refresh(pg, vendored, dry_run=False)
    assert second.changed is False
    assert _table(pg) == snapshot


def test_refresh_replaces_changed_rows(pg):
    old = [Interval("A", "SP500", D("2020-01-02"), None, "A")]
    new = [
        Interval("A", "SP500", D("2020-01-02"), D("2021-01-04"), "A"),
        Interval("B", "SP500", D("2021-01-04"), None, "B"),
    ]
    cmd.refresh(pg, old, dry_run=False)
    assert cmd.refresh(pg, new, dry_run=False).changed
    assert [row[0] for row in _table(pg)] == ["A", "B"]


def test_refresh_dry_run_writes_nothing(pg, vendored):
    result = cmd.refresh(pg, vendored, dry_run=True)
    assert result.changed
    assert _table(pg) == []


# --- CLI wiring --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["--dry-run", "universe", "refresh"],
        ["universe", "--dry-run", "refresh"],
        ["universe", "refresh", "--dry-run"],
    ],
)
def test_cli_parses_dry_run_anywhere(argv):
    from seer_engine import cli

    args = cli.build_parser().parse_args(argv)
    assert args.command == "universe" and args.action == "refresh"
    assert args.dry_run is True
    assert args.data_dir == m.DATA_DIR


def test_cli_check_defaults():
    from seer_engine import cli

    args = cli.build_parser().parse_args(["universe", "check"])
    assert args.action == "check" and args.dry_run is False
