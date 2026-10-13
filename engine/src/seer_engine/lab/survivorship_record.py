"""The committed survivorship grid, read as evidence the promote gate can act on.

**Why this module exists.** Every lab result is measured on ``engine/.research``, which prices
about 59% of the index-member days of 1996-2015 -- overwhelmingly the survivors, because the
companies that went bankrupt, were bought or renamed are the ones the free feed could not serve.
In October 2026 one month of EODHD history filled 522 of them into a second store and 102 variants
were re-run on both (``lab survivorship``, ``docs/lab/survivorship/``). That report's headline was
an average: momentum drawdowns about 2.6 points deeper.

The average was never applied to the one bar it threatens. Design doc §17 applies it, and measured
per variant rather than averaged the picture is sharper than the average suggested: of the 28
variants whose dev-store drawdown clears ``MAX_DRAWDOWN``, **11 cross it on the fuller history**,
and the per-variant deltas run -9.03 to +14.44 points. No single haircut can stand in for the
measurement -- which is exactly why this module reads the recorded numbers instead of applying a
constant.

**Why a CSV and not the lab database.** A survivorship re-run is a *report*, never a trial: mixing
price fingerprints inside one method's trial set is what ``hardgate`` exists to refuse, so these
numbers have no home in ``trials`` and never will. ``docs/lab/survivorship/grid.csv`` is the
committed record, it is append-only in practice, and reading it costs no store and no network --
which matters, because ``engine/.research-sv`` is not on every machine and cannot be rebuilt
offline. The gate must still be able to refuse on this evidence on a laptop that never bought the
month.

**Absence is not evidence.** A variant with no row here has not been measured on the fuller
history; it has not passed. :func:`sv_drawdown` returns ``None`` for it and the gate's rule is
written so that ``None`` does not refuse -- the §17 rule asks for a recorded figure under the bar
*or* a dev figure low enough that no plausible delta reaches it, and only the first is mechanical.
Refusing every unmeasured variant would block the whole lab on a store most machines do not have.
What this module makes impossible is promoting a variant **measured and found over the bar**.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

#: The committed grid: repo root / docs / lab / survivorship / grid.csv.
#: ``parents[4]`` is the repo root -- lab, seer_engine, src, engine, <root>.
GRID_PATH = Path(__file__).resolve().parents[4] / "docs" / "lab" / "survivorship" / "grid.csv"

#: The ``store`` column's value for the fuller history. Mirrors
#: ``survivorship_check.SV_LABEL``; imported rather than restated would make this module depend on
#: one that loads research stores, which is the dependency this module exists to avoid.
SV_LABEL = "survivorship"


@lru_cache(maxsize=1)
def _grid(path_text: str) -> dict[tuple[str, str], float]:
    """``(method_id, candidate_id) -> fuller-history max drawdown``, for rows that have one.

    Cached on the path's text because the committed grid does not change inside a process, and the
    gate may ask about several variants in one run. A missing file is an empty mapping, not an
    error: a checkout that has never run ``lab survivorship`` is a normal checkout.
    """
    path = Path(path_text)
    if not path.is_file():
        return {}
    out: dict[tuple[str, str], float] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("store") != SV_LABEL:
                continue
            raw = (row.get("max_drawdown") or "").strip()
            if not raw:
                continue
            try:
                dd = float(raw)
            except ValueError:
                continue  # a malformed cell is an unmeasured variant, not a crash
            method, candidate = row.get("method_id"), row.get("candidate_id")
            if method and candidate:
                out[(method, candidate)] = dd
    return out


def sv_drawdown(method_id: str, candidate_id: str, path: Path | None = None) -> float | None:
    """``candidate_id``'s max drawdown on the fuller history, or ``None`` if never measured.

    ``None`` means "not measured", never "fine" -- see the module docstring. ``path`` is for tests;
    production reads :data:`GRID_PATH`.
    """
    return _grid(str(path or GRID_PATH)).get((method_id, candidate_id))


def over_bar(method_id: str, candidate_id: str, bar: float, path: Path | None = None) -> float | None:
    """The fuller-history drawdown when it is **at or above** ``bar``; ``None`` otherwise.

    Returning the number rather than a bool so the caller can quote it: a refusal that names
    "23.46% against a 20% bar" is one the owner can check against `grid.csv` himself, and a bare
    "blocked" is not.
    """
    dd = sv_drawdown(method_id, candidate_id, path)
    return dd if dd is not None and dd >= bar else None
