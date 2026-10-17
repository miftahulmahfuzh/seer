"""The cover-page parser: shares outstanding, the date they were counted, and per class.

Every 10-K and 10-Q answers the same instruction on its cover -- "Indicate the number of shares
outstanding of each of the issuer's classes of common stock, as of the latest practicable
date" -- but in free text, and filers have phrased it every way the language allows:

* "There were 1,640,183,273 shares of common stock with a par value of $0.32 outstanding at
  March 2, 1997." (GE, 10-K405)
* "As of April 30, 1998, 123,456,789 shares of the registrant's Common Stock were outstanding."
* "Class / Outstanding at July 31, 2004 -- Common Stock, $.01 par value / 1,234,567,890"
  (a two-column table, which an HTML cover renders as cells)
* "Class A Common Stock 100,234,567 shares; Class B Common Stock 50,123,456 shares" (several
  classes, which are summed when they are common equity and kept per class)
* "approximately 1.6 billion shares", "(in thousands) 1,640,183", "Common Stock: 123.4 million"
* and typos (``outstandng``, ``oustanding``), stray spaces inside numbers, ``&nbsp;``/``&#160;``
  entities and tags splitting a sentence across table cells.

**How.** The head of the filing is reduced to plain text (tags out, entities decoded,
whitespace collapsed) and cut down to the *cover zone*: the text up to a little past the last
"Indicate by check mark" (or the first few thousand characters when a filer left the
check-mark boilerplate out), because further in a 10-Q's income statement says "weighted
average shares outstanding" next to a number that is not the count. Inside the zone every
number of at least :data:`MIN_SHARES` (after scaling) that is not a dollar amount, a date, a
telephone/employer-id fragment or a par value, and that sits near the word "outstanding", is a
candidate; each candidate takes the class label written just before it and the nearest
plausible date (``[filed - MAX_AGE_DAYS, filed + MAX_LEAD_DAYS]``). Preferred stock, numbers
attributed to a parent ("all of which are held by ...") and duplicates of the same number are
dropped. What is left is the answer: one class, or several classes summed.

**Never guessed silently.** A parse that needed a judgment says so in ``flags`` (``no_date``,
``multi_class``, ``ambiguous``, ``scaled``, ``multi_registrant``, ``truncated``), and
``checks`` decides what a flag costs. The filing date, not the as-of date, is when a figure
became public; this module only reports the as-of date, ``history`` enforces the rule.

Pure: no network, clock or database.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, timedelta

#: Smallest share count accepted for one class, after scaling. An S&P 500 member's smallest
#: common class in 1996-2010 is in the low millions (a dual-class founder line); anything smaller
#: on a cover is a zip code, a file number, a subsidiary's 100 shares or a holder count.
MIN_SHARES = 100_000
#: Largest plausible count (no US company has had 50 billion shares outstanding).
MAX_SHARES = 50_000_000_000
#: An as-of date more than this before the filing date is not the cover count's date.
MAX_AGE_DAYS = 200
#: ... nor one after the filing date by more than this (a few filers date it the day after).
MAX_LEAD_DAYS = 10
#: How far either side of an "outstanding" a number may sit and still be the count.
NEAR_CHARS = 420
#: Text kept after the last "indicate by check mark" when bounding the cover zone.
ZONE_TAIL = 5_000
#: Cover zone when no check-mark boilerplate is found.
ZONE_DEFAULT = 12_000
#: Never look further than this into the document.
ZONE_MAX = 40_000

FLAGS = (
    "no_date",          # no plausible as-of date near the count; as_of is empty
    "multi_class",      # several common classes, summed
    "ambiguous",        # several unlabeled counts disagreed; the one nearest "outstanding" kept
    "scaled",           # the count was written in thousands/millions/billions
    "multi_registrant", # the filing covers several registrants (parent + subsidiaries)
    "truncated",        # the cached head ended before the document did
    "late_cover",       # the cover statement sat outside the usual zone (fallback search)
)


@dataclass(frozen=True)
class ClassCount:
    label: str  # "common", "class a", "class b common", "series 1", ...
    shares: int


@dataclass(frozen=True)
class Cover:
    """One parsed cover. ``shares`` is the sum of ``classes``; ``as_of`` may be None."""

    shares: int
    as_of: date | None
    classes: tuple[ClassCount, ...]
    flags: tuple[str, ...] = ()
    snippet: str = ""  # the text the count was read from, for review


@dataclass(frozen=True)
class Header:
    """What the SEC header says about the filing."""

    form: str | None
    period: date | None
    filed: date | None
    filers: tuple[str, ...]  # CIKs of every FILER block, ten digits
    names: tuple[tuple[str, tuple[str, ...]], ...] = ()  # (cik, (name, former names...))

    def names_of(self, cik: str | None) -> tuple[str, ...]:
        """The conformed and former names of ``cik`` (of the first filer when None)."""
        for key, names in self.names:
            if cik is None or key == cik:
                return names
        return ()


class CoverError(ValueError):
    """No share count could be read from the cover."""


# --- text --------------------------------------------------------------------------------

_HEADER_END = re.compile(r"</SEC-HEADER>|</IMS-HEADER>", re.I)
_DOC_START = re.compile(r"<DOCUMENT>", re.I)
_TEXT_START = re.compile(r"<TEXT>", re.I)
_FILER_CIK = re.compile(r"CENTRAL INDEX KEY:\s*(\d+)", re.I)
_FORM = re.compile(r"CONFORMED SUBMISSION TYPE:\s*(\S+)", re.I)
_PERIOD = re.compile(r"CONFORMED PERIOD OF REPORT:\s*(\d{8})", re.I)
_FILED = re.compile(r"FILED AS OF DATE:\s*(\d{8})", re.I)


def _ymd(text: str) -> date | None:
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def parse_header(raw: str) -> Header:
    m = _HEADER_END.search(raw)
    head = raw[: m.start()] if m else raw[:20_000]
    form = _FORM.search(head)
    period = _PERIOD.search(head)
    filed = _FILED.search(head)
    filers: list[str] = []
    names: list[tuple[str, tuple[str, ...]]] = []
    # Only FILER blocks count: SUBJECT COMPANY / FILED BY blocks name other parties.
    for block in re.split(r"\n\s*(?=FILER:|SUBJECT COMPANY:|FILED BY:|REPORTING-OWNER:)", head):
        if block.lstrip().upper().startswith("FILER:"):
            ciks = _FILER_CIK.findall(block)
            if not ciks:
                continue
            key = ciks[0].zfill(10)
            filers.append(key)
            found = re.findall(r"(?:FORMER\s+)?CONFORMED NAME:\s*(.+)", block)
            names.append((key, tuple(n.strip() for n in found if n.strip())))
    return Header(
        form=form.group(1) if form else None,
        period=_ymd(period.group(1)) if period else None,
        filed=_ymd(filed.group(1)) if filed else None,
        filers=tuple(dict.fromkeys(filers)),
        names=tuple(names),
    )


def first_document(raw: str) -> tuple[str, bool]:
    """The first document's text (after ``<TEXT>``) and whether its end was cached."""
    m = _DOC_START.search(raw)
    body = raw[m.end():] if m else raw
    t = _TEXT_START.search(body)
    if t and t.start() < 2_000:
        body = body[t.end():]
    end = body.find("</DOCUMENT>")
    if end >= 0:
        return body[:end], True
    return body, False


_BLOCK_TAGS = re.compile(
    r"<\s*/?\s*(?:p|div|br|tr|table|h[1-6]|li|ul|ol|center|hr|title|page)\b[^>]*>", re.I
)
_CELL_TAGS = re.compile(r"<\s*/?\s*(?:td|th)\b[^>]*>", re.I)
_ANY_TAG = re.compile(r"<[^>]{0,2000}>", re.S)
_DROP = re.compile(r"<(script|style|head)\b.*?</\1\s*>", re.I | re.S)
_SPACES = re.compile(r"[ \t\r\f\v  -​ 　]+")


def plain_text(doc: str) -> str:
    """``doc`` as plain text: tags out, entities decoded, runs of blanks collapsed.

    Plain-text filings go through the same path; their only markup is ``<PAGE>`` and the odd
    ``<S>``/``<C>`` table marker, which the tag rule removes.
    """
    text = _DROP.sub(" ", doc)
    text = _BLOCK_TAGS.sub("\n", text)
    text = _CELL_TAGS.sub(" | ", text)
    text = _ANY_TAG.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"')
    text = text.replace("”", '"').replace("–", "-").replace("—", "-")
    text = text.replace("\u0097", "-").replace("\u0096", "-").replace("\u0092", "'")
    text = _SPACES.sub(" ", text)
    text = re.sub(r" ?\n[ \n|]*", "\n", text)
    text = re.sub(r"(?: \| ?)+", " | ", text)
    return text.strip()


_CHECK = re.compile(
    r"indicate\s+by\s+(?:a\s+)?check|check\s*-?\s*mark|subject\s+to\s+such\s+filing\s+requirements",
    re.I,
)
# Where the cover ends: Part I, an index heading, or the first financial statement title.
# "Table of Contents" is not a stop -- HTML filings repeat it as a page-header link.
_PART_I = re.compile(
    r"\n\s*(?:PART\s+I\b(?!I)|(?:FORM\s+10-[KQ]\s+)?INDEX\b)"
    r"|(?:CONDENSED\s+)?CONSOLIDATED\s+(?:STATEMENTS?|BALANCE\s+SHEETS?)\s+OF"
    r"|CONSOLIDATED\s+BALANCE\s+SHEETS?"
    r"|STATEMENTS?\s+OF\s+(?:CONSOLIDATED\s+)?(?:INCOME|OPERATIONS|EARNINGS)\b",
    re.I,
)


def cover_zone(text: str) -> str:
    """The cover page's text (module docstring)."""
    head = text[:ZONE_MAX]
    marks = [m.end() for m in _CHECK.finditer(head)]
    if marks:
        end = min(len(head), marks[-1] + ZONE_TAIL)
        # Stop at a part/contents heading after the last check mark, if one comes sooner.
        stop = _PART_I.search(head, marks[-1] + 200)
        if stop and stop.start() < end:
            end = stop.start()
        return head[:end]
    stop = _PART_I.search(head, 600)
    return head[: min(ZONE_DEFAULT, stop.start() if stop else ZONE_DEFAULT)]


# --- numbers and dates ---------------------------------------------------------------------

_OUTSTANDING = re.compile(
    r"o\s?u\s?t\s?s?\s?t\s?a\s?n\s?d\s?i?\s?n\s?g|oustanding|outsanding|outstandng|outstading"
    r"|outstnading|outsstanding|outsatnding|issued\s+and\s+outstand"
    r"|total\s+number\s+of\s+shares",
    re.I,
)
# 1,640,183,273 / 1, 640,183,273 / 1.640.183.273 / 1640183273 / 123.4 (with a scale word)
_NUMBER = re.compile(
    r"(?<![\w$/])(?<!\d[.,-])(?<![a-z]\.)(\$\s*)?"
    r"(\d{1,3}(?:,\s?\d{3})+(?:\.\d+)?|\d{1,3}(?:\.\d{3}){2,}|\d+(?:\.\d+)?)"
    r"(?:\s*(?:\(\d\))?\s*(million|billion|thousand)s?\b)?",
    re.I,
)
_SCALE = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
_THOUSANDS_NOTE = re.compile(r"\(?\s*in\s+thousands\b|\(000'?s?\)|000's\s+omitted", re.I)

_MONTHS = {
    m: i + 1
    for i, names in enumerate(
        [("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
         ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
         ("september", "sept", "sep"), ("october", "oct"), ("november", "nov"),
         ("december", "dec")]
    )
    for m in names
}
_MONTH_RE = (
    r"(january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)"
)
_DATE_MDY = re.compile(
    _MONTH_RE + r"\.?\s*(\d{1,2})\s*(?:st|nd|rd|th)?\s*[,.]?\s*['`]?\s*(\d{4}|\d{2})\b", re.I
)
_DATE_DMY = re.compile(r"\b(\d{1,2})\s+" + _MONTH_RE + r"\.?,?\s+(\d{4})\b", re.I)
_DATE_NUM = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")


@dataclass(frozen=True)
class _Num:
    start: int
    end: int
    value: int
    scaled: bool


@dataclass(frozen=True)
class _Date:
    start: int
    end: int
    value: date


def _year(text: str) -> int:
    y = int(text)
    if y < 100:
        y += 1900 if y >= 50 else 2000
    return y


def find_dates(text: str) -> list[_Date]:
    out: list[_Date] = []
    for m in _DATE_MDY.finditer(text):
        try:
            out.append(_Date(m.start(), m.end(), date(_year(m.group(3)), _MONTHS[m.group(1).lower()],
                                                     int(m.group(2)))))
        except ValueError:
            continue
    for m in _DATE_DMY.finditer(text):
        try:
            out.append(_Date(m.start(), m.end(), date(int(m.group(3)), _MONTHS[m.group(2).lower()],
                                                     int(m.group(1)))))
        except ValueError:
            continue
    for m in _DATE_NUM.finditer(text):
        try:
            out.append(_Date(m.start(), m.end(), date(_year(m.group(3)), int(m.group(1)),
                                                     int(m.group(2)))))
        except ValueError:
            continue
    return sorted(out, key=lambda d: d.start)


def _digits(raw: str) -> str:
    return re.sub(r"[,\s]", "", raw)


def find_numbers(text: str, dates: list[_Date], *, thousands: bool = False) -> list[_Num]:
    """Share-count-like numbers in ``text`` (module docstring for what is excluded)."""
    spans = [(d.start, d.end) for d in dates]
    out: list[_Num] = []
    for m in _NUMBER.finditer(text):
        if m.group(1):  # a dollar amount
            continue
        s = m.start(2)
        if any(a <= s < b for a, b in spans):
            continue
        raw = m.group(2)
        nxt = text[m.end(): m.end() + 2]
        if nxt[:1] in ("-", "/", "%") or text[m.end(2): m.end(2) + 1] in ("%",):
            continue
        prev = text[max(0, s - 14): s].lower()
        if re.search(r"(\$|\bno\.|\brule|\bsection|\bitem|\bform|\bzip|file\s+number)[\s|]*$", prev):
            continue
        word = (m.group(3) or "").lower()
        scaled = False
        if "," in raw:
            value = float(_digits(raw))  # "201,593,623.521": fractional shares, kept as a float
        elif re.fullmatch(r"\d{1,3}(?:\.\d{3}){2,}", raw):
            value = float(raw.replace(".", ""))  # "1.640.183.273"
        elif "." in raw:
            if not word:
                continue  # a decimal without a scale word is not a share count
            value = float(raw)
        else:
            value = float(raw)
        if word:
            value *= _SCALE[word]
            scaled = True
        elif thousands and value < 50_000_000:
            value *= 1_000
            scaled = True
        v = int(round(value))
        if not (MIN_SHARES <= v <= MAX_SHARES):
            continue
        out.append(_Num(s, m.end(), v, scaled))
    return out


# --- labels --------------------------------------------------------------------------------

_WEAK_ANCHOR = re.compile(r"\b(?:average|weighted|options?|warrants?|units?)\b[^.]*$", re.I)
_NOT_OUTSTANDING = re.compile(r"\bauthori[sz]ed\b|\bissued\b|\breserved\b", re.I)
# A number introduced as a part of another ("This amount includes the 4,826,203 shares") or
# as a hypothetical ("pro forma ... would have been 701,245,368").
_ASIDE = re.compile(
    r"\b(?:includes?|including|excludes?|excluding)(?:\s+(?:the|approximately|an\s+aggregate\s+of))?\s*$"
    r"|\b(?:pro\s+forma|would\s+have\s+been|after\s+giving\s+effect)\b[^.]*$",
    re.I,
)
_RIGHTS = re.compile(r"(?:preferred|preference)\s+(?:share|stock)\s+purchase\s+rights?", re.I)
_PREFERRED = re.compile(r"\bpreferred|\bpreference\s+(?:stock|shares)|\bdepositary", re.I)
_CLASS = re.compile(
    r"\b(?:class|series)\s+([a-z]|[0-9]|i{1,3}|one|two)\b(?:\s+(?:common|ordinary|capital|"
    r"limited\s+voting|subordinate|special))?"
    r"|\bnon-?\s?voting\b",
    re.I,
)
_TRACKING = re.compile(r"\b([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})\s+(?:Group|Tracking)\s+"
                       r"(?:Common\s+)?Stock", re.M)
_HELD_BY = re.compile(
    r"(?:all\s+of\s+which\s+(?:are|were|is)\s+(?:held|owned)|(?:held|owned)\s+(?:of\s+record\s+)?by\s+"
    r"(?:the\s+)?(?:parent|registrant's\s+parent|(?:[A-Z][\w&.,'-]*\s+){1,4}(?:Inc|Corp|Corporation|"
    r"Company|Holdings|plc))|all\s+held\s+by|wholly[- ]owned\s+subsidiary\s+of"
    r"|no\s+public\s+(?:trading\s+)?market)",
    re.I,
)
_TREASURY = re.compile(
    r"\s*(?:shares\s+)?(?:of\s+(?:common\s+)?stock\s+)?(?:were\s+|are\s+)?(?:held\s+in\s+(?:the\s+)?treasury|"
    r"treasury\s+shares|in\s+treasury)",
    re.I,
)
_NON_AFFIL = re.compile(
    r"non-?\s?affiliates|aggregate\s+market\s+value|excluding\s+shares\s+held\s+by\s+affiliates", re.I
)
_NON_AFFIL_AFTER = re.compile(
    r"\s*(?:shares\s+)?(?:[\w']+\s+){0,4}?(?:held\s+by\s+)?non-?\s?affiliates", re.I
)


_SENTENCE_END = re.compile(
    r"(?<!\bInc)(?<!\bCo)(?<!\bNo)(?<!\bCorp)(?<!\bLtd)(?<![\s$][A-Z])[.;]\*?(?=\s)|\n\s*\n|\|"
    r"|\n(?=(?:There\s|As\s+(?:of|at)\s|On\s|At\s|The\s+(?:total\s+)?number|Number|Indicate))"
)


def _sentence_before(zone: str, pos: int) -> str:
    """The text from the start of the sentence holding ``pos`` up to it (at most 300 chars)."""
    lo = max(0, pos - 300)
    seg = zone[lo:pos]
    ends = [m.end() for m in _SENTENCE_END.finditer(seg)]
    return seg[ends[-1]:] if ends else seg


def _nonaffil_closer(zone: str, pos: int) -> bool:
    """True when the market-value sentence's words ("non-affiliates", "aggregate market
    value") sit in the same sentence as ``pos`` with no "outstanding" between them and it."""
    seg = _sentence_before(zone, pos)
    p = max((m.end() for m in _NON_AFFIL.finditer(seg)), default=-1)
    if p < 0:
        return False
    q = max((m.end() for m in _OUTSTANDING.finditer(seg)), default=-1)
    return p > q


def _preferred_after(after: str) -> bool:
    """True when the words right after a count say it is preferred stock."""
    a = after[:100].lower()
    p = min((i for i in (a.find("preferred"), a.find("preference")) if i >= 0), default=-1)
    if p < 0 or p > 70:
        return False
    c = a.find("common")
    return c < 0 or p < c


_CLASS_AFTER = re.compile(
    r"\s*shares\s+of\s+(?:the\s+)?(?:[\w.'&-]+\s+){0,3}?((?:class|series)\s+(?:[a-z]|[0-9]|i{1,3}|one|two)\b"
    r"(?:\s+(?:common|ordinary|capital|limited\s+voting|subordinate|special))?)",
    re.I,
)


def _label(before: str, after: str = "") -> str:
    """The class a count belongs to: "630,300 shares of Class B stock" names it after the
    number; otherwise the nearest class label written before it wins."""
    m = _CLASS_AFTER.match(after)
    if m:
        return re.sub(r"\s+", " ", m.group(1).lower())
    if re.match(r"\s*shares\s+of\s+(?:the\s+)?(?:[\w.'&-]+'s\s+)?common\s+stock", after, re.I):
        return "common"  # "and 560,491,503 shares of common stock": no class, whatever came before
    hits = list(_CLASS.finditer(before))
    if hits:
        last = hits[-1]
        return re.sub(r"\s+", " ", last.group(0).lower())
    t = list(_TRACKING.finditer(before))
    if t:
        return re.sub(r"\s+", " ", t[-1].group(0).lower())
    return "common"


# --- the parser ----------------------------------------------------------------------------


def parse(raw: str, filed: date | None = None, cik: str | None = None) -> Cover:
    """Read ``cik``'s share count off one cached filing head. Raises :class:`CoverError`.

    ``cik`` picks the registrant whose name selects among the counts of a cover that lists
    several (a utility holding company and its subsidiaries); None means the first filer.
    """
    header = parse_header(raw)
    filed = filed or header.filed
    doc, complete = first_document(raw)
    text = plain_text(doc)
    zone = cover_zone(text)
    kw = dict(names=header.names_of(cik), multi_registrant=len(header.filers) > 1)
    try:
        return parse_zone(zone, filed, truncated=not complete and len(zone) >= len(text) - 1, **kw)
    except CoverError as first:
        # The form's cover is not where the zone looked: some banks file the glossy annual
        # report first and the cover after it, some covers follow a contents page. Look once
        # more around the first statement-shaped sentence anywhere in the head.
        m = _STATEMENT.search(text, len(zone) // 2)
        if m is None:
            raise first
        lo = max(0, m.start() - 600)
        try:
            c = parse_zone(text[lo:m.end() + 900], filed, **kw)
        except CoverError:
            raise first from None
        return Cover(c.shares, c.as_of, c.classes, (*c.flags, "late_cover"), c.snippet)


#: The cover statement's own words, for the fallback search outside the zone.
_STATEMENT = re.compile(
    r"indicate\s+the\s+number\s+of\s+shares\s+outstanding"
    r"|number\s+of\s+(?:outstanding\s+)?shares\s+of\s+(?:the\s+)?(?:registrant'?s?\s+|its\s+)?"
    r"(?:\$?[\d.]+\s+par\s+value\s+)?common\s+stock[^.]{0,60}?outstanding"
    r"|(?:there\s+were|registrant\s+had)\s+[\d,]{9,}\s+shares",
    re.I,
)


_NAME_STOP = frozenset(
    "INC INCORPORATED CORP CORPORATION CO COMPANY THE LTD LIMITED PLC LLC LP DE NEW DEL NY NJ "
    "MD PA OH VA NV CT MA OF AND & HOLDINGS HOLDING GROUP COS COMPANIES".split()
)


def name_tokens(name: str) -> tuple[str, ...]:
    """The distinctive words of a conformed name: ``AMERICAN ELECTRIC POWER CO INC`` ->
    (AMERICAN, ELECTRIC, POWER). At most three; state suffixes (``/DE/``) dropped."""
    clean = re.sub(r"/[A-Z]{2,3}/?", " ", name.upper())
    words = re.findall(r"[A-Z0-9]+", clean)
    return tuple(w for w in words if w not in _NAME_STOP)[:3]


def names_match(label: str, names: tuple[str, ...]) -> bool:
    """True when ``label`` text carries every distinctive word of one of ``names``."""
    words = set(re.findall(r"[A-Z0-9]+", label.upper()))
    for name in names:
        toks = name_tokens(name)
        if toks and all(t in words for t in toks):
            return True
    return False


def _clause_after(zone: str, end: int) -> str:
    """The words after a count up to its "outstanding" or the sentence end (at most 120 chars)."""
    tail = zone[end:end + 120]
    m = re.search(r"outstand|\.\s+[A-Z]|;|\(|\n\s*\n", tail, re.I)
    return tail[: m.start()] if m else tail


def screen(zone: str, n: _Num) -> str | None:
    """Why the number ``n`` is not a share count, or None when it may be one."""
    before = _RIGHTS.sub("rights", _sentence_before(zone, n.start))
    after = _RIGHTS.sub("rights", zone[n.end:n.end + 140])
    clause = _clause_after(zone, n.end)
    if _nonaffil_closer(zone, n.start) or _NON_AFFIL_AFTER.match(after):
        return "non-affiliate"  # a non-affiliate share figure in the market-value sentence
    if _PREFERRED.search(before[-90:]) and not re.search(r"common", before[-50:], re.I):
        return "preferred"
    if _preferred_after(after):
        return "preferred"
    if _HELD_BY.search(re.split(r"\.\s+(?=[A-Z])|\n\s*\n|;", after[:160], maxsplit=1)[0]):
        return "held-by-parent"
    if _TREASURY.match(after):
        return "treasury"
    if _NOT_OUTSTANDING.search(clause) and not re.search(r"issued\s+and\s*$", clause, re.I):
        return "authorized-or-issued"  # "1,150,000,000 shares authorized", "... issued, of which"
    if _ASIDE.search(before[-80:]):
        return "aside"  # "This amount includes the 4,826,203 shares", "pro forma ... would have been"
    if re.match(r"\s*(?:holders|record\s+holders|shareholders|stockholders|employees|"
                r"square|acres|barrels|customers|units\s+of)", after, re.I):
        return "not-shares"
    return None


def parse_zone(zone: str, filed: date | None, *, names: tuple[str, ...] = (),
               multi_registrant: bool = False, truncated: bool = False) -> Cover:
    """The parser proper, on cover-zone text (tests feed snippets here directly)."""
    anchors = [
        m.start() for m in _OUTSTANDING.finditer(zone)
        if not _WEAK_ANCHOR.search(zone[max(0, m.start() - 45):m.start()])
    ]
    if not anchors:
        raise CoverError("no 'outstanding' on the cover")
    thousands_note = bool(_THOUSANDS_NOTE.search(zone))
    dates = find_dates(zone)
    numbers = find_numbers(zone, dates)
    flags: list[str] = []

    def near(n: _Num) -> int:
        return min(abs(a - (n.start + n.end) // 2) for a in anchors)

    cands = [n for n in numbers if near(n) <= NEAR_CHARS]
    if not cands and thousands_note:
        numbers = find_numbers(zone, dates, thousands=True)
        cands = [n for n in numbers if near(n) <= NEAR_CHARS and n.scaled]
    if not cands:
        raise CoverError("no share-count number near 'outstanding'")

    kept: list[tuple[_Num, str]] = []
    named: list[bool] = []
    seg_floor = 0
    for n in cands:
        floor, seg_floor = seg_floor, n.end
        if screen(zone, n) is not None:
            continue
        kept.append((n, _label(zone[max(0, n.start - 160):n.start], zone[n.end:n.end + 80])))
        named.append(names_match(zone[max(floor, n.start - 200):n.start], names))
    if not kept:
        raise CoverError("every number near 'outstanding' was excluded")

    # A cover listing several registrants: keep the counts written after this filer's name.
    several = multi_registrant or bool(re.search(r"\bregistrants\b", zone, re.I))
    if several and len(kept) > 1 and any(named) and not all(named):
        kept = [k for k, hit in zip(kept, named) if hit]
        flags.append("multi_registrant")
        multi_registrant = False

    # Two dated statements ("As of June 30, 2006, Ford had outstanding ..." for the market-value
    # date, then "As of February 12, 2007, ..."): keep the counts of the latest plausible date.
    if len(kept) > 1 and filed is not None:
        stamped = [(k, _nearest_date(dates, k[0])) for k in kept]
        ok = [d for _, d in stamped if d is not None and _plausible(d, filed)]
        if ok and len({d for _, d in stamped}) > 1:
            latest = max(ok)
            kept = [k for k, d in stamped if d == latest]

    # Same value twice (text and table) is one count.
    uniq: list[tuple[_Num, str]] = []
    for n, lab in kept:
        if any(n.value == u.value for u, _ in uniq):
            continue
        uniq.append((n, lab))

    # A stated total beside its parts ("54,377,800 consisting of 54,348,620 shares of Common
    # stock and 29,180 shares of Class B"): the parts are the classes, the total their check.
    if len(uniq) > 2:
        total = max(uniq, key=lambda u: u[0].value)
        parts = [u for u in uniq if u is not total]
        if abs(sum(p[0].value for p in parts) - total[0].value) <= 0.001 * total[0].value:
            uniq = parts
    elif len(uniq) == 2:
        big, small = sorted(uniq, key=lambda u: -u[0].value)
        # The second class can sit under MIN_SHARES, so the total is checked against the text.
        rest = big[0].value - small[0].value
        if rest > 0 and re.search(rf"\b{rest:,}\b|\b{rest}\b", zone[big[0].start - 300: big[0].end + 300]):
            uniq = [small, (_Num(big[0].start, big[0].end, rest, big[0].scaled), "class b")]

    labels = [lab for _, lab in uniq]
    if len(uniq) == 1:
        chosen = uniq
    elif len(set(labels)) == len(labels) and any(lab != "common" for lab in labels):
        chosen = uniq
        flags.append("multi_class")
    else:
        # Disagreeing counts that are not separate classes: keep the one nearest an anchor.
        best = min(uniq, key=lambda u: (near(u[0]), u[0].start))
        chosen = [best]
        flags.append("ambiguous")

    classes = tuple(ClassCount(lab, n.value) for n, lab in chosen)
    if any(n.scaled for n, _ in chosen):
        flags.append("scaled")
    lo = min(n.start for n, _ in chosen)
    hi = max(n.end for n, _ in chosen)
    as_of = _pick_date(dates, lo, hi, filed)
    if as_of is None:
        flags.append("no_date")
    if multi_registrant:
        flags.append("multi_registrant")
    if truncated:
        flags.append("truncated")
    snippet = re.sub(r"\s+", " ", zone[max(0, lo - 200): hi + 120]).strip()
    return Cover(
        shares=sum(c.shares for c in classes),
        as_of=as_of,
        classes=classes,
        flags=tuple(flags),
        snippet=snippet[:600],
    )


def _pick_date(dates: list[_Date], lo: int, hi: int, filed: date | None) -> date | None:
    """The plausible date written nearest the count (module docstring for the window)."""
    best: tuple[int, date] | None = None
    for d in dates:
        if filed is not None and not (
            filed - timedelta(days=MAX_AGE_DAYS) <= d.value <= filed + timedelta(days=MAX_LEAD_DAYS)
        ):
            continue
        if d.end <= lo:
            dist = lo - d.end
        elif d.start >= hi:
            dist = d.start - hi
        else:
            dist = 0
        if dist > 600:
            continue
        if best is None or dist < best[0]:
            best = (dist, d.value)
    return None if best is None else best[1]


def _plausible(d: date, filed: date) -> bool:
    return filed - timedelta(days=MAX_AGE_DAYS) <= d <= filed + timedelta(days=MAX_LEAD_DAYS)


def _nearest_date(dates: list[_Date], n: _Num, reach: int = 250) -> date | None:
    """The date written nearest ``n`` within ``reach`` characters, plausible or not."""
    best: tuple[int, date] | None = None
    for d in dates:
        dist = n.start - d.end if d.end <= n.start else d.start - n.end if d.start >= n.end else 0
        if dist <= reach and (best is None or dist < best[0]):
            best = (dist, d.value)
    return None if best is None else best[1]
