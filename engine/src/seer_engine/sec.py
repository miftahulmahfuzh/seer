"""SEC EDGAR XBRL company facts (data.sec.gov): the point-in-time fundamentals source.

The per-CIK ``companyfacts`` document is the ingest path. ``companyfacts.zip`` (1.41 GB, every
filer in one download) is the documented fallback should the scope ever widen from the 795 index
ever-members to the whole market, and nothing more: at 795 filers the per-CIK API is ~90 s end to
end under SEC's own ceiling, and a per-symbol fetch is what lets the ``fundamentals`` command
resume in the style of ``backfill_log``. Nothing here downloads the zip.

SEC's fair-access policy asks for two things and enforces both:

* A declared ``User-Agent`` carrying a contact address. It comes from the ``SEC_CONTACT_EMAIL``
  setting via ``require_contact`` and is never hardcoded, exactly as ``massive.py`` and
  ``finnhub.py`` each require their own credential through ``config``; a missing or address-less
  value raises ``config.ConfigError``, which ``cli.main`` turns into exit code 2.
* No more than 10 requests/second. Calls are spaced >= ``MIN_INTERVAL`` seconds apart, measured
  from the **end** of the previous attempt (retries included). ``MIN_INTERVAL`` is just above
  1/10 s so clock granularity cannot tip a long sweep over the ceiling. There is no API key and
  no daily quota.

**This module owns its HTTP request instead of calling ``http.get_json``, deliberately.**
``get_json`` sends ``http._session``, whose ``User-Agent`` is ``seer-engine/<version>`` with no
contact address, and it takes no ``headers`` argument -- the only way to change that header is to
mutate the module-level session, which would put this operator's address on every Massive and
Finnhub call made afterwards in the same process. Its other services are unwanted here too: its
injection points are process-global where this client needs a per-instance transport, and its URL
redaction guards a query-string key that SEC does not use. What is reused is ``http.redact``
inside ``scrub``, so the tree keeps one redaction implementation.

There is no delisted error case. EDGAR is an archive: a dead filer returns its whole history
(ATVI, CIK 718877, has 114 ``us-gaap:Assets`` facts filed 2009-08-07 through 2023-07-31). A CIK
that never filed XBRL comes back with the taxonomy simply absent -- zero facts, not an error --
or, when EDGAR holds no company-facts document for it at all, HTTP 404, which raises
``SecNotFound`` so the caller records it the way ``backfill`` records ``empty``.

``filed`` is the no-look-ahead boundary and ``accn`` is part of a fact's identity: both travel on
every ``Fact`` so the loader can expose only ``filed <= t`` and keep a restatement beside the
original instead of on top of it.

The transport is injectable (anything with ``get(url, *, params, headers, timeout)`` returning a
requests-like response, as ``requests.Session`` does), and so are ``clock`` and ``sleep``, so
tests never touch the network or wait.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import requests

from seer_engine import __version__, config, http

log = logging.getLogger(__name__)

BASE_URL = "https://data.sec.gov/api/xbrl"
CONTACT_SETTING = "SEC_CONTACT_EMAIL"
# SEC's published ceiling is 10 requests/second. 0.11 s is ~9.1 req/s: the headroom keeps a
# multi-hundred-call sweep under the ceiling even when the clock rounds a wait down.
MIN_INTERVAL = 0.11
# Measured companyfacts bodies: TWTR 1.8 MB, WRK 1.7 MB, TWX 2.3 MB, CELG 2.6 MB, ATVI 2.7 MB,
# PXD 3.4 MB, K 3.5 MB, SIVB 4.1 MB. A few MB over a slow link needs more than http.py's 30 s.
DEFAULT_TIMEOUT_S = 60.0
RETRIES = 3
BACKOFF_S = 1.0
MAX_RETRY_AFTER_S = 120.0
MAX_ERROR_BODY = 200
# The two taxonomies the fundamentals work uses. Filers also publish srt, ifrs-full and invest.
TAXONOMIES = ("us-gaap", "dei")


class SecError(RuntimeError):
    """A data.sec.gov request failed after its retries, or answered with something unusable."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class SecNotFound(SecError):
    """EDGAR holds no XBRL company-facts document for this CIK (HTTP 404).

    Not a failure. A filer that never tagged XBRL simply has nothing here, the way a symbol with
    no bars is ``empty`` rather than ``failed`` in ``backfill_log``.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, 404)


@dataclass(frozen=True, slots=True)
class Fact:
    """One XBRL fact, flattened out of ``facts.<taxonomy>.<tag>.units.<unit>[]``.

    ``filed`` is the only no-look-ahead boundary: a fact may be used on a date t only when
    ``filed <= t``. ``period_end`` is never a substitute -- a figure for the period ending
    2015-12-31 is typically filed in February 2016.

    ``accn`` is part of the identity. A restatement of the same (tag, unit, period) arrives under
    a different accession number and must be kept alongside the original, never written over it.

    ``val`` is float64. XBRL monetary facts are integral dollars and every filer in scope is far
    inside 2**53, where float64 is exact; per-share values are small decimals that carry the same
    precision the pure derivation layer will give them.
    """

    cik: str  # ten digits, zero-padded, as EDGAR writes it in a path
    taxonomy: str  # "us-gaap", "dei", ...
    tag: str  # "Assets", "Revenues", "EntityCommonStockSharesOutstanding", ...
    unit: str  # "USD", "USD/shares", "shares", ...
    period_start: date | None  # None for an instantaneous fact (a balance-sheet item)
    period_end: date
    val: float
    accn: str  # accession number, e.g. "0000718877-23-000068"
    form: str  # "10-K", "10-Q", "8-K", "20-F", ...
    fy: int | None
    fp: str | None  # "FY", "Q1".."Q4"
    filed: date
    frame: str | None  # EDGAR's own frame label, when it assigned one


@dataclass(frozen=True, slots=True)
class CompanyFacts:
    """Everything one request returned for one CIK."""

    cik: str
    entity_name: str
    facts: tuple[Fact, ...]

    def __len__(self) -> int:
        return len(self.facts)

    def tags(self) -> tuple[tuple[str, str], ...]:
        """The distinct (taxonomy, tag) pairs present, sorted. For coverage checks and logs."""
        return tuple(sorted({(f.taxonomy, f.tag) for f in self.facts}))


class Transport(Protocol):
    def get(self, url: str, *, params: dict[str, Any], headers: dict[str, str], timeout: float) -> Any: ...


class SecSource(Protocol):
    """What the ``fundamentals`` command needs, so a test can inject a fake for a Client."""

    def company_facts(self, cik: str | int, *, tags: Collection[str] | None = None) -> CompanyFacts: ...

    def company_concept(self, cik: str | int, taxonomy: str, tag: str) -> CompanyFacts: ...


def require_contact() -> str:
    """SEC_CONTACT_EMAIL, stripped; raises config.ConfigError when unset or address-less.

    SEC's fair-access policy wants a contact it can actually reach, and a User-Agent without one
    is throttled or blocked outright, so a value with no usable ``@`` is refused here rather than
    discovered at the 403.
    """
    value = config.require(CONTACT_SETTING).strip()
    local, sep, domain = value.partition("@")
    if not sep or not local or not domain:
        raise config.ConfigError(
            f"{CONTACT_SETTING} must be a contact email address SEC can reach, got {value!r}"
        )
    return value


def user_agent(contact: str) -> str:
    """The declared User-Agent: the product token plus the contact SEC's policy asks for."""
    return f"seer-engine/{__version__} ({contact})"


def scrub(text: str, contact: str | None) -> str:
    """``text`` with key/token query values redacted and the contact address removed.

    No secret is involved -- the address is the operator's own -- but SEC echoes the declared
    User-Agent back in some of its block pages, and keeping a personal address out of log lines
    and tracebacks is the same hygiene ``finnhub.scrub`` applies to its key.
    """
    out = http.redact(text)
    if contact:
        out = out.replace(contact, "REDACTED")
    return out


def cik10(cik: str | int) -> str:
    """``cik`` as EDGAR writes it in a path: ten digits, zero-padded.

    Accepts 320193, "320193", "0000320193" and "CIK0000320193". Raises ValueError on anything
    else, so a ticker that slipped through the ticker->CIK map cannot be pasted into a URL path.
    """
    text = str(cik).strip()
    if text[:3].upper() == "CIK":
        text = text[3:]
    if not text.isascii() or not text.isdigit():
        raise ValueError(f"not a CIK: {cik!r}")
    if len(text.lstrip("0")) > 10:
        raise ValueError(f"CIK is longer than 10 digits: {cik!r}")
    return text.zfill(10)


def _path_token(value: str, name: str) -> str:
    """A taxonomy or tag safe to put in an EDGAR path (``us-gaap`` keeps its hyphen)."""
    text = str(value).strip()
    if not text or not all(ch.isascii() and (ch.isalnum() or ch in "-_.") for ch in text):
        raise ValueError(f"{name} is not a usable EDGAR path segment: {value!r}")
    return text


def _retry_after(resp: Any) -> float | None:
    headers = getattr(resp, "headers", None) or {}
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        return min(MAX_RETRY_AFTER_S, max(0.0, float(value)))
    except (TypeError, ValueError):
        return None


def _default_transport(contact: str) -> Transport:
    """A session of this client's own.

    ``http._session`` is deliberately left alone: it serves Massive and Finnhub, which must not
    send this contact address.
    """
    session = requests.Session()
    session.headers["User-Agent"] = user_agent(contact)
    session.headers["Accept"] = "application/json"
    session.headers["Accept-Encoding"] = "gzip, deflate"
    return session


def _day(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    out = float(value)
    return out if math.isfinite(out) else None


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _fact(cik: str, taxonomy: str, tag: str, unit: str, raw: Any) -> Fact | None:
    """One ``units.<unit>[]`` element as a Fact, or None when it lacks val/end/accn/form/filed."""
    if not isinstance(raw, dict):
        return None
    val = _number(raw.get("val"))
    period_end = _day(raw.get("end"))
    filed = _day(raw.get("filed"))
    accn = _text(raw.get("accn"))
    form = _text(raw.get("form"))
    if val is None or period_end is None or filed is None or accn is None or form is None:
        return None
    fy = raw.get("fy")
    if isinstance(fy, bool) or not isinstance(fy, int):
        fy = None
    return Fact(
        cik=cik,
        taxonomy=taxonomy,
        tag=tag,
        unit=unit,
        period_start=_day(raw.get("start")),
        period_end=period_end,
        val=val,
        accn=accn,
        form=form,
        fy=fy,
        fp=_text(raw.get("fp")),
        filed=filed,
        frame=_text(raw.get("frame")),
    )


def _collect(cik: str, taxonomy: str, tag: str, units: Any, out: list[Fact]) -> int:
    """Append every parsable fact under one tag's ``units`` map; return the number skipped."""
    if not isinstance(units, dict):
        return 0 if units is None else 1
    skipped = 0
    for unit, rows in units.items():
        if not isinstance(unit, str) or not isinstance(rows, list):
            skipped += 1
            continue
        for raw in rows:
            fact = _fact(cik, taxonomy, tag, unit, raw)
            if fact is None:
                skipped += 1
                continue
            out.append(fact)
    return skipped


def _entity_name(payload: Mapping[str, Any]) -> str:
    name = payload.get("entityName")
    return name.strip() if isinstance(name, str) else ""


def _check_cik(payload: Mapping[str, Any], cik: str, what: str) -> None:
    """Refuse a body whose own ``cik`` is not the one requested (a mis-routed document).

    A silently wrong document would write another company's fundamentals under this symbol, so
    the echo is checked rather than trusted. A body that omits ``cik`` is accepted: the path is
    authoritative.
    """
    raw = payload.get("cik")
    if raw is None:
        return
    try:
        echoed = cik10(raw)
    except ValueError:
        return
    if echoed != cik:
        raise SecError(f"{what} CIK{cik}: body is for CIK{echoed}")


def _sorted(facts: list[Fact]) -> tuple[Fact, ...]:
    """Deterministic order, so two parses of one document produce identical rows."""
    return tuple(
        sorted(facts, key=lambda f: (f.taxonomy, f.tag, f.unit, f.period_end, f.filed, f.accn))
    )


def parse_company_facts(
    payload: Mapping[str, Any],
    cik: str | int,
    *,
    taxonomies: Collection[str] | None = TAXONOMIES,
    tags: Collection[str] | None = None,
) -> CompanyFacts:
    """A ``companyfacts/CIK##########.json`` body as a CompanyFacts.

    ``taxonomies`` narrows which ``facts.<taxonomy>`` branches are read (None reads every one);
    ``tags`` narrows to a set of tag names across those branches (None keeps all). Both are
    applied during the walk rather than afterwards because one filer's document measured 1.7 MB
    to 4.1 MB and holds tens of thousands of facts, of which the concept ladder uses a handful.

    Rows missing ``val``, ``end``, ``accn``, ``form`` or ``filed`` are dropped and counted, never
    guessed at. ``cik`` comes from the request path and wins over the body, which is only checked
    for agreement.
    """
    key = cik10(cik)
    _check_cik(payload, key, "companyfacts")
    want_tax = None if taxonomies is None else {str(t) for t in taxonomies}
    want_tags = None if tags is None else {str(t) for t in tags}
    facts_node = payload.get("facts")
    out: list[Fact] = []
    skipped = 0
    if isinstance(facts_node, dict):
        for taxonomy, tag_map in facts_node.items():
            if not isinstance(taxonomy, str):
                skipped += 1
                continue
            if want_tax is not None and taxonomy not in want_tax:
                continue
            if not isinstance(tag_map, dict):
                skipped += 1
                continue
            for tag, node in tag_map.items():
                if not isinstance(tag, str):
                    skipped += 1
                    continue
                if want_tags is not None and tag not in want_tags:
                    continue
                if not isinstance(node, dict):
                    skipped += 1
                    continue
                skipped += _collect(key, taxonomy, tag, node.get("units"), out)
    if skipped:
        log.debug("sec: CIK%s companyfacts: skipped %d malformed rows", key, skipped)
    return CompanyFacts(cik=key, entity_name=_entity_name(payload), facts=_sorted(out))


def parse_company_concept(
    payload: Mapping[str, Any], cik: str | int, taxonomy: str, tag: str
) -> CompanyFacts:
    """A ``companyconcept/CIK##########/<taxonomy>/<tag>.json`` body as a CompanyFacts.

    The concept document is the narrow variant: one tag, ``units`` at the top level, no ``facts``
    wrapper. It yields the same Fact rows, so a cheap spot check and a full ingest compare
    directly.
    """
    key = cik10(cik)
    _check_cik(payload, key, "companyconcept")
    out: list[Fact] = []
    skipped = _collect(key, taxonomy, tag, payload.get("units"), out)
    if skipped:
        log.debug("sec: CIK%s %s:%s: skipped %d malformed rows", key, taxonomy, tag, skipped)
    return CompanyFacts(cik=key, entity_name=_entity_name(payload), facts=_sorted(out))


class Client:
    """data.sec.gov's XBRL API: ``company_facts`` and ``company_concept``."""

    def __init__(
        self,
        contact: str,
        *,
        transport: Transport | None = None,
        base_url: str = BASE_URL,
        min_interval: float = MIN_INTERVAL,
        timeout: float = DEFAULT_TIMEOUT_S,
        retries: int = RETRIES,
        backoff: float = BACKOFF_S,
        taxonomies: Collection[str] | None = TAXONOMIES,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not contact or not contact.strip():
            raise ValueError(f"{CONTACT_SETTING} is empty; SEC requires a contact in the User-Agent")
        self.contact = contact.strip()
        self._transport = transport if transport is not None else _default_transport(self.contact)
        self.base_url = base_url.rstrip("/")
        self.min_interval = min_interval
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.taxonomies = taxonomies
        self._clock = clock
        self._sleep = sleep
        self._last_call: float | None = None
        self.calls = 0

    def __repr__(self) -> str:
        return f"Client(base_url={self.base_url!r})"

    def _pace(self) -> None:
        if self._last_call is None:
            return
        wait = self._last_call + self.min_interval - self._clock()
        if wait > 0:
            log.debug("sec: waiting %.3fs for the 10 req/s ceiling", wait)
            self._sleep(wait)

    def _get(self, path: str) -> Any:
        """GET ``path`` under base_url and return the decoded JSON body.

        Connection errors, timeouts, 429 and 5xx are retried up to ``retries`` times with
        exponential backoff (a longer numeric Retry-After wins, capped at MAX_RETRY_AFTER_S).
        404 raises SecNotFound at once; any other non-200 raises SecError at once.
        """
        url = f"{self.base_url}{path}"
        headers = {
            "User-Agent": user_agent(self.contact),
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }
        attempt = 0
        while True:
            attempt += 1
            self._pace()
            log.info("sec GET %s", path)
            self.calls += 1
            status: int | None = None
            retry_after: float | None = None
            try:
                resp = self._transport.get(url, params={}, headers=headers, timeout=self.timeout)
            except requests.RequestException as exc:
                message = f"{type(exc).__name__}: {exc}"
                retryable = True
            else:
                status = resp.status_code
                if status == 200:
                    try:
                        return resp.json()
                    except ValueError:
                        raise SecError(f"non-JSON response from sec {path}", status) from None
                if status == 404:
                    raise SecNotFound(f"sec {path}: EDGAR has no XBRL facts for this CIK")
                message = f"HTTP {status} from sec {path}: {str(resp.text)[:MAX_ERROR_BODY]}"
                if status == 403:
                    message += f" (SEC refuses an undeclared client; check {CONTACT_SETTING})"
                retryable = status == 429 or status >= 500
                retry_after = _retry_after(resp)
            finally:
                self._last_call = self._clock()
            message = scrub(message, self.contact)
            if not retryable or attempt > self.retries:
                raise SecError(message, status)
            delay = self.backoff * (2 ** (attempt - 1))
            if retry_after is not None:
                delay = max(delay, retry_after)
            log.warning("sec: %s; retry %d/%d in %.1fs", message, attempt, self.retries, delay)
            self._sleep(delay)

    def company_facts(
        self, cik: str | int, *, tags: Collection[str] | None = None
    ) -> CompanyFacts:
        """Every XBRL fact EDGAR holds for ``cik``, in the client's taxonomies, flattened.

        ``tags`` narrows the parse to those tag names; pass the concept ladder's tags to keep the
        row count in hand (a document measured 1.7 MB for TWTR to 4.1 MB for SIVB). A filer with
        no us-gaap facts yields an empty tuple -- that is a real answer, not an error. Raises
        SecNotFound when EDGAR holds no company-facts document, SecError on anything else.
        """
        key = cik10(cik)
        payload = self._get(f"/companyfacts/CIK{key}.json")
        if not isinstance(payload, dict):
            raise SecError(f"sec companyfacts CIK{key}: unexpected {type(payload).__name__}", 200)
        out = parse_company_facts(payload, key, taxonomies=self.taxonomies, tags=tags)
        log.info(
            "sec companyfacts CIK%s (%s): %d facts over %d tags",
            key, out.entity_name, len(out.facts), len(out.tags()),
        )
        return out

    def company_concept(self, cik: str | int, taxonomy: str, tag: str) -> CompanyFacts:
        """One concept's facts for ``cik`` -- the cheap single-tag variant, for spot checks.

        ``company_concept(718877, "us-gaap", "Assets")`` is ATVI's 114 Assets facts, filed
        2009-08-07 through 2023-07-31.
        """
        key = cik10(cik)
        tax = _path_token(taxonomy, "taxonomy")
        name = _path_token(tag, "tag")
        payload = self._get(f"/companyconcept/CIK{key}/{tax}/{name}.json")
        if not isinstance(payload, dict):
            raise SecError(
                f"sec companyconcept CIK{key} {tax}:{name}: unexpected {type(payload).__name__}", 200
            )
        out = parse_company_concept(payload, key, tax, name)
        log.info("sec companyconcept CIK%s %s:%s: %d facts", key, tax, name, len(out.facts))
        return out
