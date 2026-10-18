"""The EDGAR Archives downloader: quarterly indexes and the head of each periodic report.

Network edge of the shares history; everything it writes goes under the gitignored
``engine/.cache/edgar/`` (:data:`CACHE_DIR`), like ``engine/.cache/eodhd/``:

* ``index/<YYYY>Q<n>.master.gz`` -- EDGAR's quarterly master index, byte for byte.
* ``filings/<YYYY>/<accession>.txt.gz`` -- the **head** of the filing's full submission text:
  the SEC header and its first document (the 10-K or 10-Q itself), cut at that document's
  ``</DOCUMENT>`` or at :data:`MAX_HEAD` bytes, whichever comes first, then gzipped.
  ``<accession>.missing`` marks a filing EDGAR answered 404 for, so a re-run does not ask again.
* ``xbrl/<cik>.json`` -- ``data.sec.gov`` ``companyconcept`` for
  ``dei:EntityCommonStockSharesOutstanding``, the 2009+ overlap the parser is checked against;
  ``<cik>.missing`` when the filer never tagged it.
* ``xbrl-instance/<cik>/<accession>.json.gz`` -- the share-count facts of a 2009+ filing's own
  XBRL instance (``shares.instance``), for the per-class csv (``shares.classes``). Only the parsed
  facts are kept, never the instance: the cover facts sit at the end of a 1-4 MB document, so the
  whole of it is downloaded (gzip on the wire, ~60 KB for Meta's 1.2 MB) and parsed in memory.
  ``<accession>.missing`` holds the reason a filing gave none (no filing index, no instance file,
  an unreadable instance), so a re-run does not ask again.

**Why only the head.** The share count is on the cover page, the first page of the first
document. A full submission is the whole annual report with every exhibit (GE's 1997 10-K405 is
375 KB of text; a 2008 one with HTML exhibits runs to megabytes), and EDGAR ignores ``Range``
requests, so the body is streamed and the connection dropped once the head is in hand. The cap
is generous because an HTML cover can sit behind tens of kilobytes of inline styling.

**Resumable and idempotent.** A file's presence is the record that it is done: a re-run skips
every accession already cached (or marked missing), so an interrupted sweep restarts where it
stopped and a finished one costs no requests. Writes go to a ``.tmp`` sibling and are renamed
into place, so a kill mid-write never leaves a truncated file that looks complete.

**SEC's fair-access rules** (``sec`` module docstring) bind here too: a declared User-Agent with
``SEC_CONTACT_EMAIL``, and fewer than 10 requests a second. Downloads run on a small thread pool
so one slow response does not idle the sweep, but every request start passes one shared
:class:`Pacer`, so the pool as a whole never exceeds the ceiling. A 403 from the Archives is
SEC's rate-limit block (it lasts about ten minutes); the worker sleeps it out and retries.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import requests

from seer_engine import config, sec
from seer_engine.shares import edgar_index, instance
from seer_engine.shares.edgar_index import FilingRef

log = logging.getLogger(__name__)

CACHE_DIR = config.REPO_ROOT / "engine" / ".cache" / "edgar"
ARCHIVES = "https://www.sec.gov/Archives/"
CONCEPT_URL = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/dei/EntityCommonStockSharesOutstanding.json"
)

#: Bytes of decoded submission text kept per filing (module docstring).
MAX_HEAD = 200_000
#: Seconds between request starts across the whole pool: ~8.3 req/s, under SEC's 10.
MIN_INTERVAL = 0.12
WORKERS = 6
TIMEOUT_S = 60.0
RETRIES = 4
BACKOFF_S = 2.0
#: How long to wait out an Archives 403 (SEC's rate-limit block).
BLOCK_WAIT_S = 600.0
END_DOC = b"</DOCUMENT>"
#: Cache directory of the per-class instance facts, and the version of their JSON layout
#: (``instance.Fact.to_json``); a file of another version is refused, never misread.
INSTANCE_DIR = "xbrl-instance"
INSTANCE_CACHE_VERSION = 1


class FetchError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class Pacer:
    """Spaces request starts at least ``interval`` seconds apart across threads."""

    def __init__(self, interval: float, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.interval = interval
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            start = max(now, self._next)
            self._next = start + self.interval
        if start > now:
            self._sleep(start - now)


def filing_path(cache: Path, ref: FilingRef) -> Path:
    return cache / "filings" / f"{ref.filed.year}" / f"{ref.accession}.txt.gz"


def missing_path(cache: Path, ref: FilingRef) -> Path:
    return cache / "filings" / f"{ref.filed.year}" / f"{ref.accession}.missing"


def index_path(cache: Path, year: int, quarter: int) -> Path:
    return cache / "index" / f"{year}Q{quarter}.master.gz"


def xbrl_path(cache: Path, cik: str) -> Path:
    return cache / "xbrl" / f"{cik}.json"


def instance_path(cache: Path, cik: str, accession: str) -> Path:
    return cache / INSTANCE_DIR / cik / f"{accession}.json.gz"


def instance_missing_path(cache: Path, cik: str, accession: str) -> Path:
    return cache / INSTANCE_DIR / cik / f"{accession}.missing"


def filing_dir(ref: FilingRef) -> str:
    """The filing's Archives directory, relative to :data:`ARCHIVES`:
    ``edgar/data/1326801/0001326801-14-000032.txt`` -> ``edgar/data/1326801/000132680114000032/``."""
    parent, _, _ = ref.path.rpartition("/")
    return f"{parent}/{ref.accession.replace('-', '')}/"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}.{threading.get_ident()}")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def head_of(chunks: Iterable[bytes], limit: int = MAX_HEAD) -> tuple[bytes, bool]:
    """The submission text up to and including the first ``</DOCUMENT>``, or ``limit`` bytes.

    Returns (head, complete): ``complete`` is True when the first document ended inside the
    limit. Pure, so the cut is tested without a network.
    """
    buf = bytearray()
    for chunk in chunks:
        if not chunk:
            continue
        scan_from = max(0, len(buf) - len(END_DOC))
        buf.extend(chunk)
        at = buf.find(END_DOC, scan_from)
        if at >= 0:
            end = at + len(END_DOC)
            return bytes(buf[: min(end, limit)]), end <= limit
        if len(buf) >= limit:
            return bytes(buf[:limit]), False
    return bytes(buf), False


class Archive:
    """A paced, retrying client for www.sec.gov/Archives and data.sec.gov. Thread-safe."""

    def __init__(self, contact: str, *, pacer: Pacer | None = None,
                 session_factory: Callable[[], requests.Session] | None = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.contact = contact
        self.pacer = pacer or Pacer(MIN_INTERVAL)
        self._factory = session_factory or self._session
        self._local = threading.local()
        self._sleep = sleep
        self.calls = 0
        self._count_lock = threading.Lock()

    def _session(self) -> requests.Session:
        s = requests.Session()
        s.headers["User-Agent"] = sec.user_agent(self.contact)
        s.headers["Accept-Encoding"] = "gzip, deflate"
        return s

    def _s(self) -> requests.Session:
        s = getattr(self._local, "s", None)
        if s is None:
            s = self._local.s = self._factory()
        return s

    def get(self, url: str, *, head: bool = False) -> bytes | None:
        """The body of ``url`` (only its head when ``head``), or None on 404."""
        attempt = 0
        while True:
            attempt += 1
            self.pacer.wait()
            with self._count_lock:
                self.calls += 1
            try:
                with self._s().get(url, timeout=TIMEOUT_S, stream=head) as resp:
                    status = resp.status_code
                    if status == 200:
                        if head:
                            body, _ = head_of(resp.iter_content(chunk_size=65536))
                            return body
                        return resp.content
                    if status == 404:
                        return None
                    message = f"HTTP {status} from {url}"
            except requests.RequestException as exc:
                status = None
                message = f"{type(exc).__name__}: {exc}"
            message = sec.scrub(message, self.contact)
            if attempt > RETRIES:
                raise FetchError(message, status)
            if status == 403:
                log.warning("edgar: %s -- SEC rate block; waiting %.0fs", message, BLOCK_WAIT_S)
                self._sleep(BLOCK_WAIT_S)
            elif status is None or status == 429 or status >= 500:
                delay = BACKOFF_S * 2 ** (attempt - 1)
                log.warning("edgar: %s; retry %d/%d in %.0fs", message, attempt, RETRIES, delay)
                self._sleep(delay)
            else:
                raise FetchError(message, status)


def fetch_indexes(archive: Archive, cache: Path,
                  qs: Sequence[tuple[int, int]] | None = None) -> list[FilingRef]:
    """Every wanted-form filing of the horizon's quarters, downloading indexes not yet cached.

    A quarter that is still open on EDGAR (the current one) would change after caching, so
    callers pass only closed quarters: the cover horizon ends in 2010, and the per-class reader
    asks ``edgar_index.closed_quarters``.
    """
    refs: list[FilingRef] = []
    for year, quarter in qs or edgar_index.quarters():
        path = index_path(cache, year, quarter)
        if not path.exists():
            body = archive.get(edgar_index.index_url(year, quarter))
            if body is None:
                raise FetchError(f"no master index for {year}Q{quarter}", 404)
            _atomic_write(path, body)
            log.info("edgar: index %dQ%d %d bytes", year, quarter, len(body))
        refs.extend(edgar_index.read_master_gz(path.read_bytes()))
    return refs


@dataclass
class Tally:
    wanted: int = 0
    cached: int = 0
    fetched: int = 0
    missing: int = 0
    failed: list[str] = field(default_factory=list)
    bytes_raw: int = 0
    seconds: float = 0.0


def fetch_filings(archive: Archive, cache: Path, refs: Sequence[FilingRef], *,
                  workers: int = WORKERS, progress_every: int = 500) -> Tally:
    """Download the head of every ref's submission not yet cached (module docstring)."""
    by_acc: dict[str, FilingRef] = {}
    for ref in refs:
        by_acc.setdefault(ref.accession, ref)
    tally = Tally(wanted=len(by_acc))
    todo = []
    for ref in by_acc.values():
        if filing_path(cache, ref).exists() or missing_path(cache, ref).exists():
            tally.cached += 1
        else:
            todo.append(ref)
    log.info("edgar: %d filings wanted, %d cached, %d to fetch", tally.wanted, tally.cached, len(todo))
    t0 = time.monotonic()
    lock = threading.Lock()

    def one(ref: FilingRef) -> tuple[FilingRef, bytes | None]:
        return ref, archive.get(ARCHIVES + ref.path, head=True)

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, ref) for ref in todo]
        for fut in as_completed(futures):
            try:
                ref, body = fut.result()
            except FetchError as exc:
                with lock:
                    tally.failed.append(str(exc))
                continue
            if body is None:
                _atomic_write(missing_path(cache, ref), b"404\n")
                tally.missing += 1
            else:
                _atomic_write(filing_path(cache, ref), gzip.compress(body, compresslevel=6))
                tally.fetched += 1
                tally.bytes_raw += len(body)
            done += 1
            if done % progress_every == 0:
                rate = done / max(1e-9, time.monotonic() - t0)
                log.info("edgar: %d/%d fetched (%.1f/s, eta %.0f min)", done, len(todo), rate,
                         (len(todo) - done) / max(rate, 1e-9) / 60)
    tally.seconds = time.monotonic() - t0
    return tally


def fetch_xbrl(archive: Archive, cache: Path, ciks: Iterable[str]) -> Tally:
    """``companyconcept`` dei shares for every CIK not yet cached (2009+ overlap check)."""
    tally = Tally()
    t0 = time.monotonic()
    for key in ciks:
        tally.wanted += 1
        path = xbrl_path(cache, key)
        miss = path.with_suffix(".missing")
        if path.exists() or miss.exists():
            tally.cached += 1
            continue
        try:
            body = archive.get(CONCEPT_URL.format(cik=key))
        except FetchError as exc:
            tally.failed.append(str(exc))
            continue
        if body is None:
            _atomic_write(miss, b"404\n")
            tally.missing += 1
        else:
            _atomic_write(path, body)
            tally.fetched += 1
            tally.bytes_raw += len(body)
    tally.seconds = time.monotonic() - t0
    return tally


@dataclass(frozen=True)
class InstanceFetch:
    """What one filing's instance gave: its file name and share facts, or why there are none."""

    name: str
    facts: tuple[instance.Fact, ...] | None
    size: int = 0
    reason: str = ""


def fetch_instance(archive: Archive, ref: FilingRef) -> InstanceFetch:
    """The filing's index, then its instance, parsed (two requests; module docstring).

    Raises :class:`FetchError` only for what a retry may fix (the network, SEC's rate block);
    a filing that has no instance, or whose instance is unreadable, answers with a reason.
    """
    base = ARCHIVES + filing_dir(ref)
    listing = archive.get(base + "index.json")
    if listing is None:
        return InstanceFetch("", None, reason="no filing index")
    try:
        name = instance.instance_name(instance.filing_files(listing))
    except instance.InstanceError as exc:
        return InstanceFetch("", None, reason=f"bad filing index: {exc}")
    if name is None:
        return InstanceFetch("", None, reason="no XBRL instance")
    body = archive.get(base + name)
    if body is None:
        return InstanceFetch(name, None, reason=f"{name} not found")
    try:
        facts = instance.parse(body)
    except instance.InstanceError as exc:
        return InstanceFetch(name, None, len(body), reason=f"{name} unreadable: {exc}")
    return InstanceFetch(name, tuple(facts), len(body))


def instance_blob(name: str, facts: Sequence[instance.Fact]) -> bytes:
    """The cache file for one filing's facts: versioned JSON, gzipped."""
    doc = {"version": INSTANCE_CACHE_VERSION, "instance": name, "facts": [f.to_json() for f in facts]}
    text = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return gzip.compress(text.encode("utf-8"), compresslevel=6)


def read_instance(path: Path) -> tuple[str, tuple[instance.Fact, ...]]:
    """A cached filing's (instance file name, share facts)."""
    try:
        doc = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise instance.InstanceError(f"{path}: unreadable cache file: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("version") != INSTANCE_CACHE_VERSION:
        raise instance.InstanceError(f"{path}: not a version-{INSTANCE_CACHE_VERSION} cache file")
    facts = doc.get("facts")
    if not isinstance(facts, list):
        raise instance.InstanceError(f"{path}: no facts list")
    return str(doc.get("instance", "")), tuple(instance.Fact.from_json(f) for f in facts)


def read_missing(path: Path) -> str:
    """The reason a ``.missing`` marker records."""
    return path.read_text(encoding="utf-8").strip() or "missing"


def fetch_instances(archive: Archive, cache: Path, refs: Sequence[FilingRef], *,
                    workers: int = WORKERS, progress_every: int = 500) -> Tally:
    """Download and parse the instance of every ref not yet cached (module docstring).

    A filing made jointly by several wanted filers is fetched once and cached under each.
    """
    by_acc: dict[str, list[FilingRef]] = {}
    for ref in refs:
        group = by_acc.setdefault(ref.accession, [])
        if all(r.cik != ref.cik for r in group):
            group.append(ref)
    tally = Tally(wanted=len(by_acc))
    todo: list[list[FilingRef]] = []
    for acc, group in by_acc.items():
        if all(instance_path(cache, r.cik, acc).exists()
               or instance_missing_path(cache, r.cik, acc).exists() for r in group):
            tally.cached += 1
        else:
            todo.append(group)
    log.info("edgar: %d instances wanted, %d cached, %d to fetch", tally.wanted, tally.cached, len(todo))
    t0 = time.monotonic()

    def one(group: list[FilingRef]) -> tuple[list[FilingRef], InstanceFetch]:
        return group, fetch_instance(archive, group[0])

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, group) for group in todo]
        for fut in as_completed(futures):
            try:
                group, got = fut.result()
            except FetchError as exc:
                tally.failed.append(str(exc))
                continue
            for r in group:
                if got.facts is None:
                    _atomic_write(instance_missing_path(cache, r.cik, r.accession),
                                  (got.reason + "\n").encode("utf-8"))
                else:
                    _atomic_write(instance_path(cache, r.cik, r.accession),
                                  instance_blob(got.name, got.facts))
            if got.facts is None:
                tally.missing += 1
            else:
                tally.fetched += 1
                tally.bytes_raw += got.size
            done += 1
            if done % progress_every == 0:
                rate = done / max(1e-9, time.monotonic() - t0)
                log.info("edgar: %d/%d instances (%.1f/s, eta %.0f min)", done, len(todo), rate,
                         (len(todo) - done) / max(rate, 1e-9) / 60)
    tally.seconds = time.monotonic() - t0
    return tally


def read_head(path: Path) -> str:
    """A cached filing head as text. EDGAR text is ASCII with stray latin-1 bytes."""
    return gzip.decompress(path.read_bytes()).decode("latin-1")


def cache_size(cache: Path) -> tuple[int, int]:
    """(files, bytes) under ``cache``."""
    n = size = 0
    for root, _dirs, files in os.walk(cache):
        for name in files:
            n += 1
            size += os.path.getsize(os.path.join(root, name))
    return n, size
