"""Pre-2009 shares outstanding: the EDGAR index and filing-head cut, the cover-page parser on real
cover snippets of different shapes, the checks, the point-in-time lookup and the 2009 XBRL join,
the market-value helpers, and the vendored csv's invariants (no network)."""

from __future__ import annotations

import gzip
from dataclasses import dataclass
from datetime import date

import pytest

from seer_engine import cik as c
from seer_engine import membership as m
from seer_engine.shares import checks, cover, edgar_index, fetch, history

D = date.fromisoformat


# --- index ------------------------------------------------------------------------------------

MASTER = """Description:           Master Index of EDGAR Dissemination Feed
Last Data Received:    March 31, 1997

CIK|Company Name|Form Type|Date Filed|Filename
--------------------------------------------------------------------------------
40545|GENERAL ELECTRIC CO|10-K405|1997-03-21|edgar/data/40545/0000040545-97-000005.txt
40545|GENERAL ELECTRIC CO|SC 13G|1997-02-12|edgar/data/40545/0000040545-97-000001.txt
40545|GENERAL ELECTRIC CO|10-K/A|1997-03-28|edgar/data/40545/0000040545-97-000009.txt
51143|INTERNATIONAL BUSINESS MACHINES CORP|10-K|1997-03-27|edgar/data/51143/0000912057-97-010483.txt
"""


def test_master_index_keeps_original_periodic_reports_only():
    refs = edgar_index.read_master_gz(gzip.compress(MASTER.encode("latin-1")))
    assert [(r.cik, r.form, r.accession) for r in refs] == [
        ("0000040545", "10-K405", "0000040545-97-000005"),
        ("0000051143", "10-K", "0000912057-97-010483"),
    ]
    assert refs[0].filed == D("1997-03-21")
    assert refs[0].path == "edgar/data/40545/0000040545-97-000005.txt"


def test_quarters_span_the_horizon():
    qs = edgar_index.quarters()
    assert qs[0] == (1995, 4) and qs[-1] == (2010, 4) and len(qs) == 61


def _row(symbol, cik, start, end=None):
    return c.CikRow(symbol, cik, D(start), D(end) if end else None, "X", "manual", "n")


def test_windows_lead_the_first_member_day_and_stop_at_the_last():
    ivs = [m.Interval("AAA", "SP500", D("2000-06-01"), D("2003-01-01"), "AAA"),
           m.Interval("BBB", "NDX", D("2000-01-01"), None, "BBB")]
    index = {"AAA": (_row("AAA", "0000000001", "1990-01-01"),),
             "BBB": (_row("BBB", "0000000002", "1990-01-01"),)}
    wins = edgar_index.windows(ivs, index)
    assert list(wins) == ["0000000001"]  # NDX-only filers are not wanted
    w = wins["0000000001"]
    assert w.start == D("1999-04-28")  # 400 days ahead of the first member day
    assert w.end == D("2003-01-01") and w.symbols == ("AAA",)


def test_select_keeps_joint_filings_once_per_wanting_filer():
    wins = {"0000000001": edgar_index.Window("0000000001", D("2000-01-01"), D("2001-01-01"), ("A",)),
            "0000000002": edgar_index.Window("0000000002", D("2000-01-01"), D("2001-01-01"), ("B",))}
    ref = edgar_index.FilingRef("0000000001", D("2000-05-01"), "10-Q", "0000000001-00-000001", "A",
                                "edgar/data/1/0000000001-00-000001.txt")
    twin = edgar_index.FilingRef("0000000002", D("2000-05-01"), "10-Q", "0000000001-00-000001", "B",
                                 "edgar/data/2/0000000001-00-000001.txt")
    late = edgar_index.FilingRef("0000000001", D("2002-05-01"), "10-Q", "0000000001-02-000001", "A",
                                 "edgar/data/1/0000000001-02-000001.txt")
    assert edgar_index.select([ref, twin, late, ref], wins) == [ref, twin]


# --- the filing head --------------------------------------------------------------------------


def test_head_stops_at_the_first_document_end():
    chunks = [b"<SEC-HEADER>h</SEC-HEADER><DOCUMENT>cover</DOC", b"UMENT><DOCUMENT>exhibit"]
    head, complete = fetch.head_of(chunks, limit=1000)
    assert head.endswith(b"</DOCUMENT>") and b"exhibit" not in head and complete


def test_head_is_cut_at_the_limit():
    head, complete = fetch.head_of([b"x" * 600, b"y" * 600], limit=1000)
    assert len(head) == 1000 and not complete


def test_pacer_spaces_request_starts():
    now = [0.0]
    slept: list[float] = []

    def sleep(s):
        slept.append(s)
        now[0] += s

    p = fetch.Pacer(0.12, clock=lambda: now[0], sleep=sleep)
    for _ in range(3):
        p.wait()
    assert slept == pytest.approx([0.12, 0.12])


# --- the cover parser: real snippets ----------------------------------------------------------


def parse(text, filed="1997-04-01", names=()):
    return cover.parse_zone(text, D(filed), names=names)


def test_ge_there_were_n_shares_outstanding_at_date():
    snip = ("There were 1,640,183,273 shares of common stock with a par value of\n$0.32 outstanding "
            "at March 2, 1997. These shares, which constitute all of the\nvoting stock of the "
            "registrant, had an aggregate market value on March 3, 1997,\nof $170.6 billion.")
    got = parse(snip)
    assert (got.shares, got.as_of, got.flags) == (1_640_183_273, D("1997-03-02"), ())


def test_two_column_table_with_par_value_and_day_month_year():
    snip = ("Indicate the number of shares outstanding of each of the issuer's classes of common "
            "stock, as\nof the latest practicable date.\nClass\nOutstanding at 26 January 2009 | \n"
            "Common Stock, $1 par value\n209,653,292 | \nAIR PRODUCTS AND CHEMICALS, INC.")
    got = parse(snip, "2009-01-28")
    assert (got.shares, got.as_of) == (209_653_292, D("2009-01-26"))


def test_dot_leaders_and_no_par_value_hyphen():
    snip = ("Number of shares of Registrant's common stock,\noutstanding as of June 30, 1999 "
            "....................113,870,783\n2\n")
    assert parse(snip, "1999-08-10").shares == 113_870_783
    snip2 = ("Indicate\nthe number of shares outstanding of each of the registrant's classes of common\n"
             "stock, as of the latest practicable date.\nCommon\nStock, no par value-643,585,128 shares\n"
             "(July\n31,\n2007)\n")
    got = parse(snip2, "2007-08-29")
    assert (got.shares, got.as_of) == (643_585_128, D("2007-07-31"))


def test_market_value_sentence_and_preferred_are_not_the_count():
    snip = ("The aggregate market value of the voting stock held by non-affiliates of the Registrant "
            "was approximately $8.7 billion. As of February 28, 1997, there were 200,885,052\nshares "
            "of American General's Common Stock and 2,317,701 shares of American\nGeneral's 7% "
            "Convertible Preferred Stock outstanding.")
    got = parse(snip)
    assert (got.shares, got.classes, got.flags) == (200_885_052, (cover.ClassCount("common", 200_885_052),), ())


def test_multiple_classes_are_summed_and_kept_per_class():
    snip = ("As of June 30, 2000, there were 872,670,649 shares of Class A Special Common Stock, "
            "22,624,080 shares of Class A Common Stock and 9,444,375 shares of Class B Common Stock "
            "outstanding.")
    got = parse(snip, "2000-08-14")
    assert got.shares == 872_670_649 + 22_624_080 + 9_444_375
    assert [k.label for k in got.classes] == ["class a special", "class a common", "class b common"]
    assert "multi_class" in got.flags


def test_stated_total_with_its_parts_keeps_the_parts():
    snip = ("The number of shares of Common stock of the registrant outstanding as of\nSeptember 27, "
            "1997 was 55,255,041, consisting of 54,624,741 shares of\nCommon stock and 630,300 shares "
            "of Class B stock which are identical with\nrespect to dividend and liquidation rights")
    got = parse(snip, "1997-11-07")
    assert got.shares == 55_255_041
    assert [(k.label, k.shares) for k in got.classes] == [("common", 54_624_741), ("class b", 630_300)]


def test_authorized_and_issued_counts_are_skipped():
    snip = ("As of March 31, 1999, the registrant had 1,150,000,000 and 144,118,820 respective shares "
            "of Class A and Class B Common Stock authorized, 728,460,360 shares of Class A Common "
            "Stock issued, of which 728,094,061 shares were outstanding; and no shares of Class B "
            "Common Stock were issued or outstanding.")
    assert parse(snip, "1999-05-14").shares == 728_094_061


def test_treasury_note_after_the_count_does_not_drop_it():
    snip = ("The number of shares of AMP Common Stock (without Par Value) outstanding at July\n27, 1998 "
            "was 218,601,033 (excluding shares held in the treasury of the\nCorporation, all of which "
            "are issued but not outstanding and are not entitled to\nvote).")
    got = parse(snip, "1998-08-10")
    assert (got.shares, got.as_of) == (218_601_033, D("1998-07-27"))


def test_parent_is_picked_by_name_among_subsidiaries():
    snip = ("Number of shares of common stock outstanding of the registrants at July 29, 2010 "
            "American Electric Power Company, Inc. 479,437,027 ($6.50 par value) Appalachian Power "
            "Company 13,499,500 (no par value) Columbus Southern Power Company 16,410,426 (no par value)")
    got = parse(snip, "2010-07-30", names=("AMERICAN ELECTRIC POWER CO INC",))
    assert got.shares == 479_437_027 and "multi_registrant" in got.flags


def test_scaled_words_and_fractional_shares():
    got = parse("On September 30, 2000 there were 343.8 million shares outstanding.", "2000-11-01")
    assert (got.shares, got.flags) == (343_800_000, ("scaled",))
    snip = ("Class\nOutstanding on September 30, 2008\nCommon Stock, $.625 par\nvalue\n"
            "201,593,623.521 (a)")
    assert parse(snip, "2008-11-07").shares == 201_593_624


def test_regulation_numbers_and_typos():
    snip = ("Indicate by check mark if disclosure of delinquent filers pursuant to Item 405 of "
            "Regulation S-K (Sec. 229.405 of this chapter) is not contained herein. As of "
            "January 31, 2003 there were 799,341,136 common shares oustanding.")
    assert parse(snip, "2003-02-27").shares == 799_341_136


def test_html_entities_and_cells_become_plain_text():
    doc = ("<html><body><p>As of April&nbsp;30,&#160;1998, the Corporation had</p>"
           "<table><tr><td>771,789,413</td><td>common shares without par value outstanding.</td>"
           "</tr></table></body></html>")
    text = cover.plain_text(doc)
    got = parse(text, "1998-05-12")
    assert (got.shares, got.as_of) == (771_789_413, D("1998-04-30"))


def test_no_count_raises():
    with pytest.raises(cover.CoverError):
        parse("Earnings per share are computed using the weighted average number of shares.")


def test_parse_reads_the_header_and_first_document_only():
    raw = ("<SEC-HEADER>\nCONFORMED SUBMISSION TYPE:\t10-Q\nFILED AS OF DATE:\t\t19980512\n"
           "FILER:\n\tCOMPANY DATA:\n\t\tCOMPANY CONFORMED NAME:\t\tABBOTT LABORATORIES\n"
           "\t\tCENTRAL INDEX KEY:\t\t\t0000001800\n</SEC-HEADER>\n<DOCUMENT>\n<TYPE>10-Q\n<TEXT>\n"
           "Indicate by check mark whether the registrant (1) has filed all reports. Yes X\n"
           "As of April 30, 1998, the Corporation had 771,789,413 common shares without par value "
           "outstanding.\n</DOCUMENT>\n<DOCUMENT>\n<TYPE>EX-27\n<TEXT>\n999,999,999 shares outstanding")
    h = cover.parse_header(raw)
    assert (h.form, h.filed, h.filers) == ("10-Q", D("1998-05-12"), ("0000001800",))
    assert h.names_of("0000001800") == ("ABBOTT LABORATORIES",)
    assert cover.parse(raw).shares == 771_789_413


# --- checks -----------------------------------------------------------------------------------


def item(shares, counted, acc, close=None):
    return checks.Item(cik="0000000001", accession=acc, filed=D(counted), as_of=D(counted),
                       symbol="AAA", form="10-Q", shares=shares, classes=(), raw_close=close)


def test_xbrl_disagreement_is_fixed_with_a_note():
    a = item(1_000_000, "2009-10-01", "0000000001-09-000001")
    b = item(9_000_000, "2010-01-01", "0000000001-10-000001")  # a misread
    c = item(1_010_000, "2010-04-01", "0000000001-10-000002")  # right; the tag has a scale error
    tags = {"0000000001-09-000001": 1_002_000.0, "0000000001-10-000001": 1_005_000.0,
            "0000000001-10-000002": 1_010_000_000.0}
    out = checks.apply_xbrl([a, b, c], tags)
    assert [ok for _, ok, _ in out] == [True, False, False]
    assert b.shares == 1_005_000 and "fixed_xbrl" in b.flags and "9,000,000" in b.notes[0]
    assert c.shares == 1_010_000 and "xbrl_disagrees" in c.flags and "kept" in c.notes[0]


def test_spike_is_excluded_and_level_change_kept():
    its = [item(100e6, "2000-01-01", "a"), item(10e6, "2000-04-01", "b"), item(101e6, "2000-07-01", "c"),
           item(180e6, "2000-10-01", "d"), item(181e6, "2001-01-01", "e")]
    checks.series_checks(its, [])
    assert its[1].excluded and its[1].excluded.startswith("spike")
    assert its[3].flags == ["level"] and its[3].notes and not its[3].excluded


def test_count_already_in_post_split_shares_is_restated():
    its = [item(100_000_000, "2000-01-31", "a"), item(300_000_000, "2000-04-30", "b"),
           item(301_000_000, "2000-07-31", "c")]
    checks.series_checks(its, [checks.Split(D("2000-05-18"), 3.0)])
    assert its[1].shares == 100_000_000 and "fixed_presplit" in its[1].flags and not its[1].excluded


def test_unlisted_split_is_recognised_by_price():
    its = [item(100_000_000, "2000-01-31", "a", close=90.0), item(200_000_000, "2000-04-30", "b", close=46.0),
           item(201_000_000, "2000-07-31", "c", close=47.0)]
    checks.series_checks(its, [])
    assert "split_unlisted" in its[1].flags and not its[1].excluded


def test_market_value_bounds():
    lo = item(5_000_000, "2000-01-31", "a", close=1.0)
    hi = item(5_000_000_000, "2000-01-31", "b", close=1000.0)
    ok = item(500_000_000, "2000-01-31", "c", close=40.0)
    for x in (lo, hi, ok):
        x.norm = float(x.shares)
    checks.mv_checks([lo, hi, ok])
    assert lo.excluded and hi.excluded and not ok.excluded and not ok.flags


def test_count_printed_in_thousands_is_fixed_and_bad_price_spared():
    k = item(136_559, "2005-05-20", "a", close=60.0)  # Nordstrom 2005: "136,559 shares"
    good = item(270_000_000, "2005-08-19", "b", close=40.0)
    glitch = item(271_000_000, "2005-11-16", "c", close=0.01)  # a vendor close of one cent
    for x in (k, good, glitch):
        x.norm = float(x.shares)
    checks.unit_checks([k, good, glitch])
    checks.mv_checks([k, good, glitch])
    assert k.shares == 136_559_000 and "fixed_thousands" in k.flags and k.notes
    assert not glitch.excluded and "price_suspect" in glitch.flags


# --- the point-in-time lookup -----------------------------------------------------------------


def srow(filed, shares, as_of=None, acc=None, cik="0000000001"):
    return history.ShareRow(cik=cik, filed=D(filed), accession=acc or f"0000000001-{filed[2:4]}-00{filed[5:7]}{filed[8:]}",
                            symbol="AAA", as_of=D(as_of) if as_of else None, form="10-Q",
                            shares=shares, classes=(), flags=(), note="")


@dataclass(frozen=True)
class XF:
    symbol: str
    tag: str
    period_end: date
    val: float
    accn: str
    filed: date


INDEX = {
    "AAA": (_row("AAA", "0000000001", "1990-01-01", "2005-01-01"), _row("AAA", "0000000009", "2005-01-01")),
}


def test_a_figure_is_usable_from_its_filing_date_never_its_as_of_date():
    h = history.SharesHistory([srow("2000-05-10", 100, "2000-04-30"), srow("2000-08-10", 120, "2000-07-31")],
                              INDEX)
    assert h.shares_on("AAA", D("2000-05-09")) is None  # counted, but not yet public
    assert h.shares_on("AAA", D("2000-05-10")).shares == 100
    assert h.shares_on("AAA", D("2000-08-09")).shares == 100
    obs = h.shares_on("AAA", D("2000-08-10"))
    assert (obs.shares, obs.as_of, obs.filed, obs.source) == (120, D("2000-07-31"), D("2000-08-10"),
                                                             history.SOURCE_COVER)
    assert obs.age_days == 10


def test_the_ticker_resolves_to_its_filer_on_the_day_asked():
    h = history.SharesHistory([srow("2004-05-10", 100, "2004-04-30"),
                               srow("2005-02-10", 7, "2005-02-01", cik="0000000009", acc="0000000009-05-000001")],
                              INDEX)
    assert h.shares_on("AAA", D("2004-12-31")).shares == 100
    assert h.shares_on("AAA", D("2005-03-01")).shares == 7  # the new filer, not the old one's figure


def test_stale_figures_are_not_answered():
    h = history.SharesHistory([srow("2000-05-10", 100, "2000-04-30")], INDEX, max_age_days=400)
    assert h.shares_on("AAA", D("2001-06-04")).shares == 100  # 400 days after the count
    assert h.shares_on("AAA", D("2001-06-05")) is None
    assert history.SharesHistory([srow("2000-05-10", 100, "2000-04-30")], INDEX,
                                 max_age_days=None).shares_on("AAA", D("2001-06-05")).shares == 100


def test_xbrl_joins_after_the_seam_and_wins_the_same_report():
    rows = [srow("2009-05-01", 100, "2009-04-20", acc="0000000009-09-000001", cik="0000000009"),
            srow("2009-08-01", 101, "2009-07-20", acc="0000000009-09-000002", cik="0000000009")]
    facts = [XF("AAA", "EntityCommonStockSharesOutstanding", D("2009-07-20"), 105.0,
                "0000000009-09-000002", D("2009-08-01")),
             XF("AAA", "EntityCommonStockSharesOutstanding", D("2009-10-20"), 110.0,
                "0000000009-09-000003", D("2009-11-01"))]
    h = history.SharesHistory(rows, INDEX, facts)
    assert h.shares_on("AAA", D("2009-06-01")).source == history.SOURCE_COVER
    same = h.shares_on("AAA", D("2009-08-02"))
    assert (same.shares, same.source) == (105.0, history.SOURCE_XBRL)
    assert h.shares_on("AAA", D("2009-11-02")).shares == 110.0


def test_xbrl_classes_without_an_axis_are_summed():
    facts = [XF("G", "EntityCommonStockSharesOutstanding", D("2009-07-20"), v, "acc", D("2009-08-01"))
             for v in (240.0, 75.0, 75.0)]
    assert history.xbrl_by_symbol(facts)["G"][0].shares == 315.0


# --- market value -----------------------------------------------------------------------------


@dataclass(frozen=True)
class S:
    date: date
    ratio: float


def test_market_value_carries_the_count_across_a_split():
    obs = history.Observation("AAA", D("2000-06-01"), 100.0, D("2000-04-30"), D("2000-05-10"),
                              history.SOURCE_COVER, "x", "0000000001")
    splits = [S(D("2000-05-18"), 2.0), S(D("2003-01-01"), 3.0)]
    # Post-split raw close 50: the pre-split count is doubled, not taken as is.
    assert history.market_value(obs, D("2000-06-01"), 50.0, splits) == 200.0 * 50.0
    assert history.unadjust(10.0, D("2000-06-01"), splits) == 30.0
    assert history.unadjust(10.0, D("2000-06-01"), splits, basis=D("2002-01-01")) == 10.0
    with pytest.raises(ValueError):
        history.market_value(obs, D("2000-06-01"), 0.0, splits)


# --- the csv ----------------------------------------------------------------------------------


def test_csv_round_trip_and_invariants(tmp_path):
    rows = [srow("2000-05-10", 100, "2000-04-30"),
            history.ShareRow("0000000001", D("2000-08-10"), "0000000001-00-000810", "AAA", None, "10-Q",
                             300, (("class a", 100), ("class b", 200)), ("multi_class",), "")]
    path = tmp_path / history.SHARES_FILE
    assert history.write_rows(path, rows) == 2
    assert history.load_rows(path) == rows
    bad = [history.ShareRow("0000000001", D("2000-08-10"), "0000000001-00-000810", "AAA", None, "10-Q",
                            301, (("class a", 100), ("class b", 200)), (), "")]
    with pytest.raises(history.SharesError, match="classes sum"):
        history.check_rows(bad)
    fixed = [history.ShareRow("0000000001", D("2000-08-10"), "0000000001-00-000810", "AAA", None, "10-Q",
                              5, (), ("fixed_xbrl",), "")]
    with pytest.raises(history.SharesError, match="note"):
        history.check_rows(fixed)
    late = [srow("2000-05-10", 100, "1999-01-01")]
    with pytest.raises(history.SharesError, match="too far"):
        history.check_rows(late)


@pytest.fixture(scope="module")
def vendored() -> list[history.ShareRow]:
    return history.load_rows(history.DATA_DIR / history.SHARES_FILE)


def test_vendored_csv_loads_and_every_filer_is_in_the_map(vendored):
    index = c.load_index_with_history()
    known = {r.cik for g in index.values() for r in g if r.cik}
    assert len(vendored) > 20_000
    assert {r.cik for r in vendored} <= known


def test_vendored_flags_that_changed_a_value_say_why(vendored):
    for r in vendored:
        if any(f.startswith("fixed") or f in ("level", "split_unlisted", "split_missing", "mv_extreme")
               for f in r.flags):
            assert r.note, r


def test_vendored_point_in_time_spot_checks():
    h = history.load()
    ge = h.shares_on("GE", D("1997-04-01"))
    assert ge is not None and ge.filed <= D("1997-04-01")
    assert 1.5e9 < ge.shares < 1.8e9  # 1,640,183,273 at 1997-03-02 (10-K405)
    assert h.shares_on("GE", D("1995-01-03")) is None  # before the horizon


def test_the_latest_dated_statement_wins():
    snip = ("As of June 30, 2006, Ford had outstanding 1,809,771,835 shares of Common Stock and 70,852,076\n"
            "shares of Class B Stock. Based on the New York Stock Exchange Composite Transaction closing "
            "price ... As of February 12, 2007, Ford had outstanding 1,821,686,422 shares of Common "
            "Stock and\n70,852,076 shares of Class B Stock.")
    got = parse(snip, "2007-02-28")
    assert got.as_of == D("2007-02-12") and got.shares == 1_821_686_422 + 70_852_076


def test_non_voting_is_a_class_and_dollar_cells_are_not_counts():
    snip = ("The aggregate market value of the non-voting common equity held by non-affiliates | \n$ | \n"
            "3,237,887,735 | \nIndicate the number of shares outstanding of each of the issuer's classes "
            "of common stock, as of the latest practicable date.\nClass\nNUMBER OF SHARES OUTSTANDING\n"
            "Date\nCommon Stock | \n15,662,596 | \nDecember 31, 2002 | \nCommon Stock Non-Voting | \n"
            "124,429,677 | \nDecember 31, 2002 |")
    got = parse(snip, "2003-02-05")
    assert got.shares == 15_662_596 + 124_429_677 and "multi_class" in got.flags


def test_class_named_after_each_count():
    snip = ("As of September 30, 1997, the registrant had outstanding 135,998,932 shares of Class A "
            "common stock and 560,491,503 shares of common stock. PAGE 2")
    got = parse(snip, "1997-11-14")
    assert got.shares == 696_490_435
    assert [k.label for k in got.classes] == ["class a common", "common"]
