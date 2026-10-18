"""Multi-class company size: the class table (``shares.class_table``), its vendored csv, the
per-class XBRL rows as a third source in ``history.SharesHistory``, the attribution of classes to
listed symbols, and the store's change points over all of it (no network).

The figures are the filers' own: Meta's 10-Q of 2014-07-24, Alphabet's of 2014-07-25, Berkshire's
of 2012-11-02 and its 2009-2010 covers, Visa's of 2012-07-27, Accenture's of 2012-06-29."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from seer_engine import cik as c
from seer_engine import research
from seer_engine.backtest.market import ShareCounts
from seer_engine.shares import class_table as ct
from seer_engine.shares import history
from seer_engine.shares import store as ss

D = date.fromisoformat


@dataclass(frozen=True)
class CR:
    """Shaped like ``shares.classes.ClassRow`` (the per-class XBRL csv's row)."""

    cik: str
    symbol: str
    filed: date
    as_of: date | None
    form: str
    accession: str
    shares: int
    classes: tuple[tuple[str, int], ...]
    tagged_total: bool = False


def cr(cik, filed, as_of, accession, classes, shares=None, symbol="X"):
    return CR(cik, symbol, D(filed), D(as_of) if as_of else None, "10-Q", accession,
              shares if shares is not None else sum(n for _, n in classes), tuple(classes))


@dataclass(frozen=True)
class XF:
    symbol: str
    tag: str
    period_end: date
    val: float
    accn: str
    filed: date


def rule(cik, member, symbol, ratio, start, end=None, note="n"):
    return ct.ClassRule(cik, member, ct.class_key(member), symbol, float(ratio), D(start),
                        D(end) if end else None, note)


def _row(symbol, cik, start, end=None):
    return c.CikRow(symbol, cik, D(start), D(end) if end else None, "X", "manual", "n")


# --- class keys ------------------------------------------------------------------------------


@pytest.mark.parametrize("label, key", [
    ("us-gaap:CommonClassAMember", ("a", "class")),
    ("CommonClassAMember", ("a", "class")),
    ("class a common", ("a", "class")),
    ("class A", ("a", "class")),
    ("series a common", ("a", "class")),
    ("ClassAOrdinarySharesMember", ("a", "class")),
    ("goog:CapitalClassCMember", ("c", "class")),
    ("v:CommonClassB1Member", ("1", "b", "class")),
    ("class B-1", ("1", "b", "class")),
    ("lbtya:ClassOrdinarySharesMember", ("class",)),
    ("cmcsa:ClassaSpecialCommonStockMember", ("classa", "special")),
    ("class a special", ("a", "class", "special")),
    ("LiLACGroupMember+ClassBOrdinarySharesMember", ("b", "class", "group", "lac", "li")),
    ("ClassBOrdinarySharesMember LiLACGroupMember", ("b", "class", "group", "lac", "li")),
    ("us-gaap:CommonStockMember", ()),
])
def test_class_key_reads_member_names_and_cover_text_alike(label, key):
    assert ct.class_key(label) == key


# --- the table -------------------------------------------------------------------------------


def _csv(tmp_path, *lines):
    path = tmp_path / ct.TABLE_FILE
    path.write_text("\n".join([",".join(ct.HEADER), *lines]) + "\n", encoding="utf-8")
    return path


def test_the_loader_reads_spans_and_refuses_what_would_double_count(tmp_path):
    t = ct.load_table(_csv(tmp_path, "0000000001,class A,AAA,30,2009-01-01,2010-01-21,before",
                                     "0000000001,CommonClassAMember,AAA,1500,2010-01-21,,after"))
    assert len(t) == 2 and t.ciks() == {"0000000001"}
    assert [r.ratio for r in t.rules("0000000001", D("2010-01-20"))] == [30.0]
    assert [r.ratio for r in t.rules("0000000001", D("2010-01-21"))] == [1500.0]
    bad = {
        "overlapping": "0000000001,class A,AAA,1,2009-01-01,,x\n0000000001,class a common,BBB,1,2012-01-01,,y",
        "names no class": "0000000001,CommonStockMember,AAA,1,2009-01-01,,x",
        "finite number": "0000000001,class A,AAA,-1,2009-01-01,,x",
        "not after": "0000000001,class A,AAA,1,2009-01-01,2009-01-01,x",
        "note": "0000000001,class A,AAA,1,2009-01-01,,",
        "10 digits": "1,class A,AAA,1,2009-01-01,,x",
        "upper-case": "0000000001,class A,aaa,1,2009-01-01,,x",
    }
    for why, line in bad.items():
        with pytest.raises(ct.ClassTableError, match=why):
            ct.load_table(_csv(tmp_path, line))
    path = tmp_path / "wrong.csv"
    path.write_text("cik,member\n", encoding="utf-8")
    with pytest.raises(ct.ClassTableError, match="header"):
        ct.load_table(path)


def test_attribution_splits_converts_excludes_and_refuses_to_guess():
    t = ct.ClassTable([
        rule("0000000002", "class A", "GGL", 1, "2014-04-03"),
        rule("0000000002", "class B", "GGL", 1, "2014-04-03"),
        rule("0000000002", "class C", "GG", 1, "2014-04-03"),
        rule("0000000003", "class A", "XA", 1, "2009-01-01"),
        rule("0000000003", "class X", "XA", 0, "2009-01-01"),
    ])
    abc = (("CommonClassAMember", 283356281), ("CapitalClassCMember", 338209995),
           ("CommonClassBMember", 54825710))
    day = D("2014-07-17")
    assert t.attribute("0000000002", "GGL", day, 0, abc).shares == 283356281 + 54825710
    assert t.attribute("0000000002", "GG", day, 0, abc).shares == 338209995
    # Before the table speaks, every symbol of the filer is the whole company.
    assert t.attribute("0000000002", "GG", D("2014-01-31"), 500.0, abc[::2]).shares == 500.0
    # No class C in the count: GG is unknown, and that is no problem to report.
    assert t.attribute("0000000002", "GG", day, 0, abc[::2]) == (None, None)
    # Ratio 0: votes without economic interest.
    ax = (("CommonClassAMember", 634800693), ("acn:CommonClassXMember", 44998365))
    assert t.attribute("0000000003", "XA", D("2012-05-31"), 0, ax).shares == 634800693
    # Unknown, and why, rather than a guess.
    assert t.attribute("0000000003", "XA", D("2012-05-31"), 5, ()).problem.startswith("a figure without")
    odd = t.attribute("0000000003", "XA", D("2012-05-31"), 0, ax + (("CommonClassDMember", 3),))
    assert odd.shares is None and "CommonClassDMember" in odd.problem
    assert "names no class" in t.attribute("0000000003", "ZZ", D("2012-05-31"), 0, ax).problem
    # A filer with no row answers its total, classes or not.
    assert t.attribute("0000000009", "M", day, 7.0, abc) == (7.0, None)
    assert t.attribute(None, "M", day, 7.0, ()) == (7.0, None)


# --- the vendored table ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def vendored_table() -> ct.ClassTable:
    return ct.load_table(history.DATA_DIR / ct.TABLE_FILE)


@pytest.fixture(scope="module")
def index():
    return c.load_index_with_history()


def test_every_vendored_row_names_a_symbol_its_filer_traded_as(vendored_table, index):
    tenures = {(r.cik, r.symbol) for g in index.values() for r in g if r.cik}
    rows = [r for k in vendored_table.ciks() for r in vendored_table._by[k]]
    assert len(rows) == len(vendored_table)
    assert {(r.cik, r.symbol) for r in rows} <= tenures


def test_vendored_berkshire_and_visa_ratios(vendored_table):
    brk = "0001067983"
    a = ct.class_key("class A")

    def ratio(cik, key, on):
        (r,) = [r for r in vendored_table.rules(cik, D(on)) if r.key == key]
        return r.ratio

    assert ratio(brk, a, "2010-01-20") == 30.0
    assert ratio(brk, a, "2010-01-21") == 1500.0
    b = ct.class_key("class B")
    assert ratio("0001403161", b, "2012-07-19") == 0.4254
    assert ratio("0001403161", b, "2012-07-24") == 0.4206
    assert ratio("0001403161", b, "2015-03-19") == 1.6483
    assert ratio("0001403161", ct.class_key("class C"), "2015-03-19") == 4.0
    assert ratio("0001467373", ct.class_key("acn:CommonClassXMember"), "2012-05-31") == 0.0


def _vendored_history(index, vendored_table, class_rows=(), rows=(), xbrl=()):
    return history.SharesHistory(rows, index, xbrl, class_rows=class_rows, table=vendored_table)


def test_spot_checks_on_the_filers_own_figures(index, vendored_table):
    meta = cr("0001326801", "2014-07-24", "2014-07-22", "0001326801-14-000032",
              [("CommonClassBMember", 585003514), ("CommonClassAMember", 2015048077)])
    goog = cr("0001288776", "2014-07-25", "2014-07-17", "0001288776-14-000065",
              [("CommonClassAMember", 283356281), ("CapitalClassCMember", 338209995),
               ("CommonClassBMember", 54825710)])
    brk = cr("0001067983", "2012-11-02", "2012-10-25", "0001193125-12-449402",
             [("CommonClassBMember", 1099792631), ("CommonClassAMember", 919298)])
    visa = cr("0001403161", "2012-07-27", "2012-07-19", "0001384108-12-000008",
              [("CommonClassAMember", 527426677), ("CommonClassBMember", 245513385),
               ("CommonClassCMember", 38225522)])
    h = _vendored_history(index, vendored_table, [meta, goog, brk, visa])
    on = D("2014-08-01")
    m = h.shares_on("META", on)
    assert (m.shares, m.source, m.as_of, m.filed) == (2600051591.0, history.SOURCE_XBRL_CLASS,
                                                      D("2014-07-22"), D("2014-07-24"))
    googl, goog_c = h.shares_on("GOOGL", on), h.shares_on("GOOG", on)
    assert (googl.shares, goog_c.shares) == (338181991.0, 338209995.0)
    assert googl.shares + goog_c.shares == goog.shares  # the company, once
    assert h.shares_on("BRK.B", D("2012-11-05")).shares == 919298 * 1500 + 1099792631
    assert h.shares_on("V", D("2012-07-30")).shares == pytest.approx(
        527426677 + 245513385 * 0.4254 + 38225522)
    assert h.problems == {}


def test_berkshire_cover_rows_are_converted_at_the_ratio_of_their_count_date(index, vendored_table):
    def cover(filed, as_of, acc, a, b, label):
        return history.ShareRow("0001067983", D(filed), acc, "BRK.B", D(as_of), "10-Q", a + b,
                                ((f"class a{label}", a), (f"class b{label}", b)), ("multi_class",), "")

    rows = [cover("2009-11-06", "2009-10-29", "0001157523-09-007839", 1056884, 14845356, ""),
            cover("2010-03-01", "2010-02-18", "0001193125-10-043450", 1103764, 814349921, " common")]
    h = _vendored_history(index, vendored_table, rows=rows)
    pre = h.shares_on("BRK.B", D("2010-02-16"))  # the first member day: the pre-split count
    assert (pre.shares, pre.source) == (1056884 * 30 + 14845356, history.SOURCE_COVER)
    # The pre-split count carried across the 50-for-1 class B split meets the post-split one.
    split = [type("S", (), {"date": D("2010-01-21"), "ratio": 50.0})()]
    carried = history.shares_at(pre, D("2010-02-16"), split)
    post = h.shares_on("BRK.B", D("2010-03-01")).shares
    assert post == 1103764 * 1500 + 814349921
    assert abs(carried / post - 1) < 0.1


def test_companyfacts_class_a_alone_loses_to_the_per_class_reading_of_the_same_filing(index, vendored_table):
    acc = "0001193125-12-449402"
    class_a_only = XF("BRK.B", "EntityCommonStockSharesOutstanding", D("2012-10-25"), 919298.0, acc,
                      D("2012-11-02"))
    later = XF("BRK.B", "EntityCommonStockSharesOutstanding", D("2013-01-31"), 900000.0,
               "0001193125-13-000001", D("2013-02-20"))
    k = cr("0001067983", "2012-11-02", "2012-10-25", acc,
           [("CommonClassBMember", 1099792631), ("CommonClassAMember", 919298)])
    h = _vendored_history(index, vendored_table, [k], xbrl=[class_a_only, later])
    same = h.shares_on("BRK.B", D("2012-11-02"))
    assert (same.source, same.shares) == (history.SOURCE_XBRL_CLASS, 919298 * 1500 + 1099792631)
    # A later companyfacts figure still wins by date -- and, with no classes, cannot be split.
    assert h.shares_on("BRK.B", D("2013-02-20")) is None
    assert h.problems[("0001067983", "0001193125-13-000001", "BRK.B")].startswith("a figure without")


def test_a_bare_class_beside_axised_ones_is_named_by_a_cited_row(index, vendored_table):
    # Found refreshing the stores: Visa's 10-K of 2009-11-20 and 10-Q of 2010-02-03 tag class A
    # without the class axis (classes B and C on it), and Discovery's 10-K of 2010-02-22 tags
    # series A the same way; the instance reader keeps each as NoClassAxisMember.
    visa = cr("0001403161", "2009-11-20", "2009-11-13", "0001193125-09-239249",
              [("ClassCCommonStockMember", 129429736), ("CommonClassBMember", 245513385),
               ("NoClassAxisMember", 470210301)])
    disc = cr("0001437107", "2010-02-22", "2010-02-11", "0001193125-10-035850",
              [("ClassCCommonStockMember", 141711350), ("CommonClassBMember", 6589084),
               ("NoClassAxisMember", 135226377)])
    h = _vendored_history(index, vendored_table, [visa, disc])
    assert h.shares_on("V", D("2009-12-21")).shares == pytest.approx(
        470210301 + 245513385 * 0.5824 + 129429736)
    assert h.shares_on("WBD", D("2010-03-01")).shares == 135226377 + 6589084
    assert h.shares_on("DISCK", D("2010-03-01")).shares == 141711350
    assert h.problems == {}


def test_kinder_morgan_sponsor_classes_count_once(index, vendored_table):
    # Found refreshing the stores: KMI's classes A, B and C converted together into a fixed pool
    # of class P about the size of class A (P + A = 707.0M in 2011, the IPO's total; P reached
    # 1,035.7M once they converted, against 738.1M P + 298.7M A on 2012-10-28), so B and C
    # carry no economic interest of their own and summing them one for one overstated KMI ~14%.
    apr = cr("0001506307", "2012-05-02", "2012-04-27", "0001506307-12-000039",
             [("ClassPMember", 170922605), ("CommonClassAMember", 535972387),
              ("CommonClassBMember", 94132596), ("CommonClassCMember", 2318258)])
    oct_ = cr("0001506307", "2012-11-14", "2012-10-28", "0001506307-12-000118",
              [("ClassPMember", 738058572), ("CommonClassAMember", 298653287),
               ("CommonClassBMember", 46592538), ("CommonClassCMember", 1147540)])
    after = cr("0001506307", "2013-03-01", "2013-01-31", "0001506307-13-000015",
               [("ClassPMember", 1035669044)])
    h = _vendored_history(index, vendored_table, [apr, oct_, after])
    assert h.shares_on("KMI", D("2012-05-25")).shares == 170922605 + 535972387
    assert h.shares_on("KMI", D("2012-11-14")).shares == 738058572 + 298653287
    assert h.shares_on("KMI", D("2013-03-01")).shares == 1035669044
    assert h.problems == {} and "0001506307" not in h.summed


def test_alphabet_answers_googles_last_count_until_its_own_first_one(index, vendored_table):
    # Found refreshing the stores: GOOG/GOOGL move to Alphabet's filer on 2015-10-02, the day
    # every Google share became one Alphabet share of the same class, and Alphabet's first count
    # came with its 10-Q of 2015-10-29; the 18 sessions between went unknown.
    google = cr("0001288776", "2015-07-23", "2015-07-17", "0001288776-15-000035",
                [("CommonClassAMember", 289_418_090), ("CommonClassBMember", 52_188_287),
                 ("CapitalClassCMember", 343_928_872)])
    alphabet = cr("0001652044", "2015-10-29", "2015-10-22", "0001652044-15-000006",
                  [("CommonClassAMember", 292_000_000), ("CommonClassBMember", 50_000_000),
                   ("CapitalClassCMember", 345_000_000)])
    h = _vendored_history(index, vendored_table, [google, alphabet])
    on = D("2015-10-05")
    googl, goog = h.shares_on("GOOGL", on), h.shares_on("GOOG", on)
    assert (googl.shares, goog.shares) == (289_418_090 + 52_188_287, 343_928_872)
    assert (googl.accession, googl.cik) == ("0001288776-15-000035", "0001288776")
    later = h.shares_on("GOOGL", D("2015-10-29"))
    assert (later.shares, later.cik) == (342_000_000, "0001652044")
    # Never before the reorganisation's day, and never a count filed after ``on``.
    assert h.shares_on("GOOGL", D("2015-07-24")).cik == "0001288776"
    assert h.problems == {}


# --- the invariant: a filer the new sources do not touch answers as before --------------------

INDEX = {
    "AAA": (_row("AAA", "0000000001", "1990-01-01", "2005-01-01"), _row("AAA", "0000000009", "2005-01-01")),
    "MMM": (_row("MMM", "0000000007", "2008-01-01"),),
    "GGL": (_row("GGL", "0000000002", "2008-01-01"),),
    "GG": (_row("GG", "0000000002", "2008-01-01"),),
}


def srow(filed, shares, as_of=None, cik="0000000001", n=1, classes=()):
    return history.ShareRow(
        cik=cik, filed=D(filed), accession=f"{cik}-{filed[2:4]}-{n:06d}", symbol="AAA",
        as_of=D(as_of) if as_of else None, form="10-Q", shares=shares, classes=tuple(classes),
        flags=(), note="",
    )


ROWS = [
    srow("2000-05-10", 100, "2000-04-30", n=1),
    srow("2003-02-10", 130, None, n=3),
    srow("2005-02-10", 7, "2005-02-01", cik="0000000009", n=5),
    srow("2009-05-01", 9, "2009-04-20", cik="0000000009", n=6),
    srow("2009-05-02", 300, "2009-04-20", cik="0000000002", n=7,
         classes=(("class a", 200), ("class b", 100))),
]
FACTS = [
    XF("AAA", "EntityCommonStockSharesOutstanding", D("2009-04-20"), 9.5, "0000000009-09-000006", D("2009-05-01")),
    XF("AAA", "EntityCommonStockSharesOutstanding", D("2009-10-20"), 11.0, "0000000009-09-000007", D("2009-11-01")),
    XF("GGL", "EntityCommonStockSharesOutstanding", D("2014-01-31"), 360.0, "0000000002-14-000001", D("2014-02-03")),
]
CLASS_ROWS = [
    cr("0000000007", "2012-08-01", "2012-07-25", "0000000007-12-000001", [("CommonClassAMember", 50), ("CommonClassBMember", 25)]),
    cr("0000000007", "2013-08-01", "2013-07-25", "0000000007-13-000001", [("CommonClassAMember", 60), ("CommonClassBMember", 25)]),
    cr("0000000002", "2014-02-03", "2014-01-31", "0000000002-14-000001", [("CommonClassAMember", 250), ("CommonClassBMember", 110)]),
    cr("0000000002", "2014-04-25", "2014-04-20", "0000000002-14-000002",
       [("CommonClassAMember", 250), ("CommonClassBMember", 110), ("CapitalClassCMember", 361)]),
    cr("0000000002", "2014-07-25", "2014-07-20", "0000000002-14-000003",
       [("CommonClassAMember", 251), ("CommonClassBMember", 110), ("CommonClassDMember", 1),
        ("CapitalClassCMember", 362)]),
]
TABLE = ct.ClassTable([
    rule("0000000002", "class A", "GGL", 1, "2014-04-03"),
    rule("0000000002", "class B", "GGL", 1, "2014-04-03"),
    rule("0000000002", "class C", "GG", 1, "2014-04-03"),
])


def _answers(h, symbol, start, end):
    out, d = [], start
    while d <= end:
        o = h.shares_on(symbol, d)
        out.append(None if o is None else (o.shares, o.as_of, o.filed, o.source, o.accession, o.cik))
        d += timedelta(days=1)
    return out


def test_a_filer_with_no_table_rows_and_no_class_rows_answers_exactly_as_before():
    old = history.SharesHistory(ROWS, INDEX, FACTS)
    new = history.SharesHistory(ROWS, INDEX, FACTS, class_rows=CLASS_ROWS, table=TABLE)
    start, end = D("1999-01-01"), D("2011-12-31")
    assert _answers(old, "AAA", start, end) == _answers(new, "AAA", start, end)
    assert new.problems == {}


def test_class_axis_rows_answer_the_sum_from_their_filing_date():
    h = history.SharesHistory(ROWS, INDEX, FACTS, class_rows=CLASS_ROWS, table=TABLE)
    assert h.shares_on("MMM", D("2012-07-31")) is None  # counted, not yet public
    o = h.shares_on("MMM", D("2012-08-01"))
    assert (o.shares, o.source, o.as_of) == (75.0, history.SOURCE_XBRL_CLASS, D("2012-07-25"))
    assert h.shares_on("MMM", D("2013-08-01")).shares == 85.0
    assert h.shares_on("MMM", D("2014-08-30")) is None  # 2013-07-25 + 401 days
    # No table row: summed one for one, recorded, never a problem.
    assert "0000000007" in h.summed and not any(k[0] == "0000000007" for k in h.problems)


def test_sibling_classes_split_the_company_from_the_table_date():
    h = history.SharesHistory(ROWS, INDEX, FACTS, class_rows=CLASS_ROWS, table=TABLE)
    # Before the table speaks: both symbols are the whole company, and the per-class reading
    # beats the companyfacts tag of the same filing.
    for s in ("GGL", "GG"):
        o = h.shares_on(s, D("2014-03-01"))
        assert (o.shares, o.source) == (360.0, history.SOURCE_XBRL_CLASS)
    on = D("2014-05-01")
    assert h.shares_on("GGL", on).shares == 360.0
    assert h.shares_on("GG", on).shares == 361.0
    # A class with no row: both unknown, and the reason kept for the table's keeper.
    assert h.shares_on("GGL", D("2014-08-01")) is None and h.shares_on("GG", D("2014-08-01")) is None
    assert "CommonClassDMember" in h.problems[("0000000002", "0000000002-14-000003", "GG")]


def test_change_points_stay_exact_with_class_rows_and_the_table(tmp_path):
    h = history.SharesHistory(ROWS, INDEX, FACTS, class_rows=CLASS_ROWS, table=TABLE)
    start, end = D("1999-01-01"), D("2015-12-31")
    rows = ss.change_points(h, ["AAA", "MMM", "GGL", "GG"], start, end)
    path = tmp_path / research.SHARES_FILE
    research._write_text(path, ss.SHARES_HEADER, ss.shares_lines(rows))
    counts = ShareCounts(ss.read_shares(path, end))
    for symbol in ("AAA", "MMM", "GGL", "GG"):
        d = start
        while d <= end:
            o = h.shares_on(symbol, d)
            got = counts.count(symbol, d)
            assert (None if o is None else (o.shares, o.as_of or o.filed, o.filed, o.source)) == (
                None if got is None else tuple(got)
            ), (symbol, d)
            d += timedelta(days=1)
    assert history.SOURCE_XBRL_CLASS in ss.SOURCES
    assert any(",xbrl-class," in line for line in ss.shares_lines(rows))
