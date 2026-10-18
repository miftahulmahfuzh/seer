"""The per-class XBRL instance reader: real instance shapes trimmed to their share facts (Meta's
2014 10-Q with its two class-axis cover facts, Berkshire's default-namespace 2011 file, a 2009
``xbrl.us`` namespace), the reading rules, the filing-index pick, and the cache round trip (no
network)."""

from __future__ import annotations

from datetime import date

import pytest

from seer_engine.shares import instance

D = date.fromisoformat
META = "0001326801"

# Meta's 10-Q of 2014-07-24 (0001326801-14-000032, fb-20140630.xml), cut to the contexts and
# facts the reader looks at plus one of each kind it must ignore. The cover facts come after the
# balance-sheet ones and after a fact citing a context declared later, as in the real file.
META_2014 = b"""<?xml version="1.0" encoding="US-ASCII"?>
<!--XBRL Document Created with Wdesk from Workiva, formerly WebFilings-->
<xbrli:xbrl xmlns:dei="http://xbrl.sec.gov/dei/2013-01-31" xmlns:fb="http://www.facebook.com/20140630" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:us-gaap="http://fasb.org/us-gaap/2013-01-31" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:schemaRef xlink:href="fb-20140630.xsd" xlink:type="simple" />
  <xbrli:context id="FD2014Q2YTD">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2014-01-01</xbrli:startDate>
      <xbrli:endDate>2014-06-30</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="FI2014Q2_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassAMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2014-06-30</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="FI2014Q2_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassBMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassBMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2014-06-30</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="FI2013Q4_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassAMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2013-12-31</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="I2014Q2SharesOutstanding_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassBMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassBMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2014-07-22</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <xbrli:unit id="shares">
    <xbrli:measure>xbrli:shares</xbrli:measure>
  </xbrli:unit>
  <us-gaap:CommonStockSharesOutstanding contextRef="FI2014Q2_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassBMember" decimals="-6" id="Fact-5E940445BC685324D26D1AA65586EF9D" unitRef="shares">562000000</us-gaap:CommonStockSharesOutstanding>
  <us-gaap:CommonStockSharesOutstanding contextRef="FI2014Q2_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember" decimals="-6" id="Fact-CD3569BC3E7A0CB67A521AA655A152E4" unitRef="shares">2013000000</us-gaap:CommonStockSharesOutstanding>
  <us-gaap:CommonStockSharesOutstanding contextRef="FI2013Q4_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember" decimals="-6" id="Fact-63AA3BF9E2DFDC3FD0AB1AA6559331F8" unitRef="shares">1970000000</us-gaap:CommonStockSharesOutstanding>
  <dei:DocumentType contextRef="FD2014Q2YTD" id="Fact-7832F0FFBC2AB8405A701AA654EF855C">10-Q</dei:DocumentType>
  <dei:EntityCommonStockSharesOutstanding contextRef="I2014Q2SharesOutstanding_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassBMember" decimals="INF" id="Fact-9EDC6B302C9E595028231AA654F5CEAE" unitRef="shares">585003514</dei:EntityCommonStockSharesOutstanding>
  <dei:EntityCommonStockSharesOutstanding contextRef="I2014Q2SharesOutstanding_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember" decimals="INF" id="Fact-DB1A5E8D6A4AAB1E16671AA654F366F3" unitRef="shares">2015048077</dei:EntityCommonStockSharesOutstanding>
  <xbrli:context id="I2014Q2SharesOutstanding_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassAMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2014-07-22</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
</xbrli:xbrl>
"""


def _doc(body: str, *, dei: str = "http://xbrl.sec.gov/dei/2011-01-31",
         gaap: str = "http://fasb.org/us-gaap/2011-01-31") -> bytes:
    """A default-namespace instance (Berkshire's 2011 shape: no ``xbrli:`` prefix at all)."""
    return f"""<?xml version="1.0" encoding="us-ascii" standalone="yes"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:dei="{dei}" xmlns:us-gaap="{gaap}" xmlns:co="http://example.com/20110630">
{body}
</xbrl>
""".encode("ascii")


def _ctx(cid: str, instant: str, *members: tuple[str, str], ident: str = "0001067983") -> str:
    seg = ""
    if members:
        seg = "<segment>" + "".join(
            f'<xbrldi:explicitMember dimension="{a}">{m}</xbrldi:explicitMember>' for a, m in members
        ) + "</segment>"
    return (f'<context id="{cid}"><entity><identifier scheme="http://www.sec.gov/CIK">{ident}'
            f"</identifier>{seg}</entity><period><instant>{instant}</instant></period></context>")


def _fact(tag: str, cid: str, value: str, prefix: str = "dei", extra: str = "") -> str:
    return f'<{prefix}:{tag} contextRef="{cid}" unitRef="shares" decimals="INF"{extra}>{value}</{prefix}:{tag}>'


AXIS = "us-gaap:StatementClassOfStockAxis"
COVER = instance.COVER_TAG
BAL = instance.BALANCE_TAG


# --- parse ------------------------------------------------------------------------------------


def test_meta_2014_class_axis_cover_facts_are_kept_with_their_members():
    facts = instance.parse(META_2014)
    cover = sorted((f.dims, f.value, f.instant) for f in facts if f.tag == COVER)
    assert cover == [
        ((("StatementClassOfStockAxis", "CommonClassAMember"),), 2015048077, D("2014-07-22")),
        ((("StatementClassOfStockAxis", "CommonClassBMember"),), 585003514, D("2014-07-22")),
    ]
    assert {f.taxonomy for f in facts if f.tag == COVER} == {"dei"}
    assert sum(f.tag == BAL for f in facts) == 3
    assert all(f.identifier == META for f in facts)
    assert not any(f.tag == "DocumentType" for f in facts)


def test_meta_2014_reads_the_classes_summed_at_the_cover_date():
    got = instance.reading(instance.parse(META_2014), META)
    assert got == instance.Reading(
        tag=COVER,
        as_of=D("2014-07-22"),
        shares=2600051591,
        classes=(("CommonClassAMember", 2015048077), ("CommonClassBMember", 585003514)),
        tagged_total=False,
    )


def test_prefixes_and_taxonomy_versions_are_the_filers_choice():
    blob = _doc(
        _ctx("c1", "2009-10-20") + _fact(COVER, "c1", "1550000", prefix="d9"),
        dei="http://xbrl.us/dei/2009-01-31",
    ).replace(b'xmlns:dei="http://xbrl.us/dei/2009-01-31"', b'xmlns:d9="http://xbrl.us/dei/2009-01-31"')
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got is not None and got.shares == 1550000 and got.classes == () and got.as_of == D("2009-10-20")


def test_member_qnames_keep_their_local_name_whatever_the_prefix():
    blob = _doc(
        _ctx("a", "2014-07-17", (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("c", "2014-07-17", (AXIS, "co:CapitalClassCMember"))
        + _fact(COVER, "a", "283356281") + _fact(COVER, "c", "338209995")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got.classes == (("CapitalClassCMember", 338209995), ("CommonClassAMember", 283356281))
    assert got.shares == 621566276


def test_nil_unknown_context_and_non_positive_facts_are_dropped():
    blob = _doc(
        _ctx("c1", "2011-07-28")
        + _fact(COVER, "c1", "", extra=' xsi:nil="true"')
        + _fact(COVER, "nowhere", "100")
        + _fact(COVER, "c1", "0")
        + _fact(COVER, "c1", "-5")
    )
    assert instance.parse(blob) == []


def test_a_doctype_is_refused_before_parsing():
    with pytest.raises(instance.InstanceError, match="DOCTYPE"):
        instance.parse(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>')


def test_not_an_instance_or_not_xml_is_refused():
    with pytest.raises(instance.InstanceError, match="root element"):
        instance.parse(b"<html><body>404</body></html>")
    with pytest.raises(instance.InstanceError, match="well-formed"):
        instance.parse(META_2014[:3000])


# --- reading ----------------------------------------------------------------------------------


def test_the_cover_tag_wins_and_the_balance_sheet_tag_is_the_fallback():
    with_cover = _doc(
        _ctx("bs", "2011-06-30") + _ctx("cv", "2011-07-28")
        + _fact(BAL, "bs", "1065766445", prefix="us-gaap") + _fact(COVER, "cv", "1066954104")
    )
    got = instance.reading(instance.parse(with_cover), "0001067983")
    assert (got.tag, got.shares, got.as_of) == (COVER, 1066954104, D("2011-07-28"))
    balance_only = _doc(
        _ctx("bs", "2011-06-30") + _ctx("old", "2010-12-31")
        + _fact(BAL, "bs", "1065766445", prefix="us-gaap") + _fact(BAL, "old", "1050990468", prefix="us-gaap")
    )
    got = instance.reading(instance.parse(balance_only), "0001067983")
    assert (got.tag, got.shares, got.as_of) == (BAL, 1065766445, D("2011-06-30"))


def test_a_tagged_total_that_agrees_with_the_classes_is_the_count():
    blob = _doc(
        _ctx("t", "2012-07-19") + _ctx("a", "2012-07-19", (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("b", "2012-07-19", (AXIS, "us-gaap:CommonClassBMember"))
        + _fact(COVER, "t", "1000000500") + _fact(COVER, "a", "800000000") + _fact(COVER, "b", "200000000")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got.tagged_total and got.shares == 1000000500 and got.set_aside is None
    assert got.classes == (("CommonClassAMember", 800000000), ("CommonClassBMember", 200000000))


def test_a_bare_figure_that_is_no_total_is_a_class_without_an_axis():
    # The main class tagged bare, the other on the axis: dropping the bare one would leave the
    # company at its smaller class.
    blob = _doc(
        _ctx("t", "2012-07-19") + _ctx("b", "2012-07-19", (AXIS, "us-gaap:CommonClassBMember"))
        + _fact(COVER, "t", "800000000") + _fact(COVER, "b", "200000000")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert not got.tagged_total and got.shares == 1000000000 and got.set_aside == 800000000
    assert got.classes == (("CommonClassBMember", 200000000), (instance.NO_AXIS_MEMBER, 800000000))


def test_a_class_tagged_with_and_without_the_axis_counts_once():
    blob = _doc(
        _ctx("t", "2011-04-21") + _ctx("a", "2011-04-21", (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("b", "2011-04-21", (AXIS, "us-gaap:CommonClassBMember"))
        + _fact(COVER, "t", "1100000") + _fact(COVER, "a", "1100000") + _fact(COVER, "b", "1050000000")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got.classes == (("CommonClassAMember", 1100000), ("CommonClassBMember", 1050000000))
    assert got.shares == 1051100000 and not got.tagged_total and got.set_aside == 1100000


def test_a_tracking_group_beside_the_class_axis_keeps_both_member_names():
    track = "linta:TrackingStockAxis"
    blob = _doc(
        _ctx("ia", "2013-07-31", (track, "linta:InteractiveGroupMember"), (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("va", "2013-07-31", (track, "linta:VenturesGroupMember"), (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("a", "2013-07-31", (AXIS, "us-gaap:CommonClassAMember"))
        + _fact(COVER, "ia", "500") + _fact(COVER, "va", "40") + _fact(COVER, "a", "540")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    # Axis-name order (StatementClassOfStockAxis < TrackingStockAxis); the class-only fact beside
    # the group facts is the same shares again and is dropped.
    assert got.classes == (("CommonClassAMember+InteractiveGroupMember", 500),
                           ("CommonClassAMember+VenturesGroupMember", 40))
    assert got.shares == 540 and not got.tagged_total


def test_classes_tagged_without_an_axis_are_summed_and_repeats_counted_once():
    blob = _doc(
        _ctx("x", "2010-02-01") + _ctx("y", "2010-02-01")
        + _fact(COVER, "x", "240000000") + _fact(COVER, "y", "80000000") + _fact(COVER, "y", "80000000")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got.shares == 320000000 and got.classes == ()


def test_a_stale_class_comparative_is_dropped():
    blob = _doc(
        _ctx("a", "2014-07-22", (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("b_old", "2013-12-31", (AXIS, "us-gaap:CommonClassBMember"))
        + _fact(COVER, "a", "2015048077") + _fact(COVER, "b_old", "577000000")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got.classes == (("CommonClassAMember", 2015048077),) and got.shares == 2015048077


def test_another_registrant_and_other_axes_are_not_the_filers_count():
    blob = _doc(
        _ctx("sub", "2011-07-28", ident="0000012345")
        + _ctx("legal", "2011-07-28", ("dei:LegalEntityAxis", "co:SubsidiaryMember"))
        + _ctx("two", "2011-07-28", (AXIS, "us-gaap:CommonClassAMember"), ("us-gaap:RangeAxis", "co:XMember"))
        + _fact(COVER, "sub", "5") + _fact(COVER, "legal", "6") + _fact(COVER, "two", "7")
    )
    assert instance.reading(instance.parse(blob), "0001067983") is None
    # The same file read for the co-registrant answers its own count.
    assert instance.reading(instance.parse(blob), "0000012345").shares == 5


# --- the filing index -------------------------------------------------------------------------


def _index(*names: str) -> bytes:
    import json

    return json.dumps({"directory": {"name": "/Archives/x", "item": [
        {"name": n, "type": "text.gif", "size": "1"} for n in names]}}).encode()


def test_instance_name_traditional_inline_and_rendered_filings():
    meta_2014 = ["0001326801-14-000032.txt", "0001326801-14-000032-xbrl.zip", "fb-20140630.xml",
                 "fb-20140630.xsd", "fb-20140630_cal.xml", "fb-20140630_def.xml", "fb-20140630_lab.xml",
                 "fb-20140630_pre.xml", "FilingSummary.xml", "R1.htm"]
    assert instance.instance_name(instance.filing_files(_index(*meta_2014))) == "fb-20140630.xml"
    meta_2021 = ["0001326801-21-000049-xbrl.zip", "fb-20210630.xsd", "fb-20210630_cal.xml",
                 "fb-20210630_htm.xml", "fb-20210630_lab.xml", "FilingSummary.xml"]
    assert instance.instance_name(meta_2021) == "fb-20210630_htm.xml"
    brk_2011 = ["brka-20101231.xml", "brka-20101231.xsd", "defnref.xml", "R1.xml", "R2.xml",
                "brka-20101231_pre.xml"]
    assert instance.instance_name(brk_2011) == "brka-20101231.xml"
    assert instance.instance_name(["d123.htm", "FilingSummary.xml"]) is None
    assert instance.instance_name(["a.xml", "b.xml"]) is None


def test_a_filing_index_that_is_not_json_is_refused():
    with pytest.raises(instance.InstanceError):
        instance.filing_files(b"<html>")
    with pytest.raises(instance.InstanceError):
        instance.filing_files(b'{"directory": {}}')


# --- cache form -------------------------------------------------------------------------------


def test_fact_json_round_trip():
    facts = instance.parse(META_2014)
    assert [instance.Fact.from_json(f.to_json()) for f in facts] == facts
    with pytest.raises(instance.InstanceError):
        instance.Fact.from_json({"x": "dei", "t": COVER, "v": 0, "i": None, "e": "", "d": [], "y": False})
