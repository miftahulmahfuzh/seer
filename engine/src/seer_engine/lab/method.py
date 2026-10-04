"""A lab method: one idea, 1–6 fixed variants (method lab design §2).

A method is one file ``seer_engine/lab/methods/mNNNN_<slug>.py`` exporting ``METHOD``. New
signal logic is an ``Allocator`` in the same file (the protocol in ``strategies.allocator``);
an existing allocator with new params is a variation. Everything else (``TradeRules``, the
book engine, costs, dividends, whole shares) is reused unchanged.

``config_text``/``config_digest`` identify a trial by what it *does* (rules, allocator id,
params), not by its name: the same configuration under a new id is still a re-run, and the
lab database refuses it. Allocator ids are therefore unique across lab methods, and a method
file is frozen once it has run (``source_sha``; tests/test_lab_methods.py checks both).
"""

from __future__ import annotations

import hashlib
import importlib
import pkgutil
import re
from dataclasses import dataclass, field
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
class Method:
    """One lab idea and its pre-registered variants.

    ``hypothesis``: why it should beat SPY under design §1; ``expected_failure``: the way it
    most likely fails. Both are written before the run and frozen with the commit.
    Candidate ids are ``<id>-<suffix>`` and every candidate's family is the method id.
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
        ids: set[str] = set()
        digests: set[str] = set()
        for c in self.candidates:
            if not isinstance(c, Candidate):
                raise TypeError(f"{self.id}: candidates must be Candidate values")
            if not c.id.startswith(self.id + "-"):
                raise ValueError(f"{self.id}: candidate id {c.id} must start with {self.id}-")
            if c.family != self.id:
                raise ValueError(f"{self.id}: candidate {c.id} must have family {self.id}, got {c.family}")
            if c.id in ids:
                raise ValueError(f"{self.id}: candidate id {c.id} appears twice")
            digest = config_digest(c)
            if digest in digests:
                raise ValueError(f"{self.id}: candidate {c.id} repeats another variant's configuration")
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
