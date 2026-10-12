"""A lab method: one idea, 1-6 fixed variants (method lab design §2), plus its amendments.

A method is one file ``seer_engine/lab/methods/mNNNN_<slug>.py`` exporting ``METHOD``. New
signal logic is an ``Allocator`` in the same file (the protocol in ``strategies.allocator``);
an existing allocator with new params is a variation. Everything else (``TradeRules``, the
book engine, costs, dividends, whole shares) is reused unchanged.

``config_text``/``config_digest`` identify a trial by what it *does* (rules, allocator id,
params), not by its name: the same configuration under a new id is still a re-run, and the
lab database refuses it. Allocator ids are therefore unique across lab methods.

A method file used to be **frozen outright** once it had run: ``source_sha`` was written once and
every reader compared the file on disk against that one hash. Since 2026-10-12 it is frozen
*against its latest recorded sha* instead, and may grow ``Amendment`` blocks -- see ``Amendment``
for why the rule changed and what replaced it. ``methods.source_sha`` is still written exactly
once and ``methods_source_sha_once`` still refuses to let it move; the newer shas live in
``method_amendments``, one append-only row per amendment, and ``store.latest_source_sha`` is the
one place that answers "which sha is this file supposed to hash to today".
(tests/test_lab_methods.py checks the sha equality and the digest equality, which are the two
halves of the replacement.)
"""

from __future__ import annotations

import hashlib
import importlib
import pkgutil
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import ModuleType

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.registry import _canon

METHOD_ID = re.compile(r"M\d{4}")
MODULE_NAME = re.compile(r"m(\d{4})_[a-z0-9_]+")
SOURCE_KINDS: tuple[str, ...] = ("paper", "blog", "github", "knowledge", "variation")
MAX_VARIANTS = 6


def config_text(c: Candidate) -> str:
    """Canonical text of what ``c`` does: rules, allocator id and params (not id or family)."""
    return "\n".join(
        (f"rules={_canon(c.rules)}", f"allocator=<{c.allocator.id}>", f"params={_canon(c.params)}")
    ) + "\n"


def config_digest(c: Candidate) -> str:
    return hashlib.sha256(config_text(c).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Amendment:
    """More pre-registered variants of a method that has already run (design §2, 2026-10-12).

    **Why the freeze had to become something a file can grow under.** The old rule -- a method
    file is frozen once it has run, and a change is a new variation method id -- was written when
    the luck gate counted trial *rows*, so a new id cost the lab nothing it was not already paying.
    Under the ``methods`` policy (``store.DSR_POLICY``, since 2026-10-08) it costs the whole lab
    one more independent look. Measured 2026-10-12 on the committed database (130 methods, 354 dev
    trials): ``store.pending_gate`` prices a brand-new method at N = 75 against N = 74 for another
    variant of a method that has already run -- and that +1 is applied retroactively, to every
    recorded trial's published verdict. Asking one more question of an idea the lab has already
    counted should cost nothing, and under this policy it does.

    **What an amendment is.** More variants of the *same* idea, declared in the same method file,
    recorded under the same ``method_id``. It is pre-registered exactly as the original was: the
    commit that adds this block is the pre-registration (``lab run --amend`` refuses an
    uncommitted or dirty file through ``registry_problem``), and ``why``, ``hypothesis`` and
    ``expected_failure`` are written before any result is seen and frozen with that commit.

    **What replaced the freeze.** Two checks, together stronger than the one they replace:

    1. the file on disk hashes to the **latest** sha the lab recorded for it --
       ``store.latest_source_sha``: the newest ``method_amendments`` row, falling back to
       ``methods.source_sha``, which is never rewritten and whose trigger stays;
    2. every candidate a recorded trial names still digests to the ``config_digest`` that trial
       holds (``prereg.check_source``, ``remeasure.preflight``, and
       ``test_every_recorded_configuration_still_digests_to_its_recorded_digest``).

    Check 1 alone never covered an edit to an *imported* params dataclass or allocator, which can
    move a recorded digest without touching this file at all; check 2 is what covers that, and the
    two were always meant to be read together. Check 2 was measured on the committed lab on
    2026-10-12: 63 method files, 0 sha mismatches, 0 digests drifted.

    ``added`` is the day the block was written. ``why`` is one line naming the new question, for a
    reader who later finds two batches of trials under one id and needs to know why. ``candidates``
    is 1..``MAX_VARIANTS`` of them, counted **per amendment and not per method lifetime** (plan
    Decision D3): the cap is design §2's "one idea with 1-6 fixed variants per run", and an
    amendment is a run. ``Method.__post_init__`` additionally refuses a candidate id or a
    configuration that any other variant of this method -- original or amendment -- already uses.
    """

    added: date
    why: str
    hypothesis: str
    expected_failure: str
    candidates: tuple[Candidate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.added, date):
            raise TypeError(f"an amendment's added must be a date, got {type(self.added).__name__}")
        for name in ("why", "hypothesis", "expected_failure"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"an amendment's {name} must be a non-empty str")
        if not isinstance(self.candidates, tuple):
            raise TypeError("an amendment's candidates must be a tuple")
        if not 1 <= len(self.candidates) <= MAX_VARIANTS:
            raise ValueError(
                f"an amendment carries 1..{MAX_VARIANTS} candidates, got {len(self.candidates)}"
            )


@dataclass(frozen=True)
class Method:
    """One lab idea and its pre-registered variants.

    ``hypothesis``: why it should beat SPY under design §1; ``expected_failure``: the way it
    most likely fails. Both are written before the run and frozen with the commit.
    Candidate ids are ``<id>-<suffix>`` and every candidate's family is the method id.

    ``amendments`` are the later, separately pre-registered batches of variants of this same idea
    (``Amendment``). They are a tuple in declaration order and the lab records them in that order,
    one ``method_amendments`` row each, so the record is always a prefix of the file. Every reader
    that asks "what variants does this method have" wants ``all_candidates()``, not ``candidates``:
    ``candidates`` is the original batch and nothing else.
    """

    id: str
    name: str
    family: str
    source_kind: str
    source_ref: str
    hypothesis: str
    expected_failure: str
    candidates: tuple[Candidate, ...]
    parent_id: str | None = None
    seen_keys: tuple[str, ...] = field(default=())
    amendments: tuple[Amendment, ...] = field(default=())

    def all_candidates(self) -> tuple[Candidate, ...]:
        """Every variant this method has ever pre-registered: the originals, then each amendment's.

        In declaration order, which is the order the lab recorded them in, so a reader can map a
        recorded trial back onto the block that pre-registered it by position as well as by id.
        Identical to ``candidates`` for a method with no amendment, which is every method file
        committed before 2026-10-12.
        """
        out: list[Candidate] = list(self.candidates)
        for a in self.amendments:
            out.extend(a.candidates)
        return tuple(out)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or METHOD_ID.fullmatch(self.id) is None:
            raise ValueError(f"method id must look like M0001, got {self.id!r}")
        for name in ("name", "family", "hypothesis", "expected_failure"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{self.id}: {name} must be a non-empty str")
        if self.source_kind not in SOURCE_KINDS:
            raise ValueError(f"{self.id}: source_kind must be one of {SOURCE_KINDS}, got {self.source_kind!r}")
        if self.source_kind != "knowledge" and not self.source_ref.strip():
            raise ValueError(f"{self.id}: a {self.source_kind} method needs a source_ref (URL, citation or parent)")
        if self.source_kind == "variation" and not self.parent_id:
            raise ValueError(f"{self.id}: a variation needs parent_id")
        if not isinstance(self.candidates, tuple) or not 1 <= len(self.candidates) <= MAX_VARIANTS:
            raise ValueError(f"{self.id}: 1..{MAX_VARIANTS} candidates, got {len(self.candidates)}")
        if not isinstance(self.amendments, tuple):
            raise TypeError(f"{self.id}: amendments must be a tuple of Amendment values")
        for a in self.amendments:
            if not isinstance(a, Amendment):
                raise TypeError(f"{self.id}: amendments must be Amendment values, got {type(a).__name__}")
        # One pass over the originals and then each amendment, sharing the id and digest sets: a
        # candidate may not repeat an id or a configuration that any *other* batch of this same
        # method already used, or `has_trial` would refuse the run after the backtest was paid for.
        # The empty `where` for the originals keeps their messages byte-identical to the ones this
        # validation gave before amendments existed.
        ids: set[str] = set()
        digests: set[str] = set()
        batches: list[tuple[str, tuple[Candidate, ...]]] = [("", self.candidates)]
        for i, a in enumerate(self.amendments, start=1):
            batches.append((f" amendment {i} ({a.added.isoformat()})", a.candidates))
        for where, cands in batches:
            for c in cands:
                if not isinstance(c, Candidate):
                    raise TypeError(f"{self.id}{where}: candidates must be Candidate values")
                if not c.id.startswith(self.id + "-"):
                    raise ValueError(f"{self.id}{where}: candidate id {c.id} must start with {self.id}-")
                if c.family != self.id:
                    raise ValueError(f"{self.id}{where}: candidate {c.id} must have family {self.id}, got {c.family}")
                if c.id in ids:
                    raise ValueError(f"{self.id}{where}: candidate id {c.id} appears twice")
                digest = config_digest(c)
                if digest in digests:
                    raise ValueError(f"{self.id}{where}: candidate {c.id} repeats another variant's configuration")
                ids.add(c.id)
                digests.add(digest)
        for key in self.seen_keys:
            if not isinstance(key, str) or ":" not in key:
                raise ValueError(f"{self.id}: seen key {key!r} must look like kind:value")


def methods_package() -> ModuleType:
    return importlib.import_module("seer_engine.lab.methods")


def discover() -> dict[str, tuple[Method, Path]]:
    """Method id -> (METHOD, file path) for every ``mNNNN_*.py`` module, sorted by id.

    ValueError when a module's number disagrees with its METHOD.id or two modules share an id.
    """
    pkg = methods_package()
    out: dict[str, tuple[Method, Path]] = {}
    for info in pkgutil.iter_modules(pkg.__path__):
        m = MODULE_NAME.fullmatch(info.name)
        if m is None:
            continue
        module = importlib.import_module(f"{pkg.__name__}.{info.name}")
        method = getattr(module, "METHOD", None)
        if not isinstance(method, Method):
            raise TypeError(f"{module.__name__} has no METHOD = Method(...)")
        if method.id != f"M{m.group(1)}":
            raise ValueError(f"{module.__name__}: file number M{m.group(1)} != METHOD.id {method.id}")
        if method.id in out:
            raise ValueError(f"two method files claim {method.id}")
        out[method.id] = (method, Path(module.__file__).resolve())
    return dict(sorted(out.items()))


def source_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
