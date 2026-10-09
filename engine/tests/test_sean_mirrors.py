"""Sean's TypeScript constants are hand mirrors of engine constants. This is the guard.

``web/lib/sean`` runs in the browser and on the Next server, so a handful of engine values are
retyped there: the owner's contribution schedule, the resize band, the rule sets that resize, and
the fallback USD/IDR rate. Each carries a comment naming its Python twin -- and until this file,
nothing failed when one side moved. A mirror nobody checks is a number that is right on the day it
is written and silently wrong afterwards, which is the shape of defect this repo keeps paying for.

WHY A MIRROR AT ALL, AND WHAT THE ALTERNATIVES ARE. Three patterns already exist here, best first:

1. PUBLISH, DON'T MIRROR. ``web/data/lab.json``'s ``gate`` block is resolved at export time from
   ``tuning``/``store`` and pinned by ``test_lab_snapshot.py``, which is why no Sera page retypes a
   bar. Anything the web needs from a Python constant should travel this way. A constant guarded
   here should be PROMOTED to that pattern the first time it actually has to change -- that is when
   the mirror would otherwise bite, and when the work pays for itself.
2. A SHARED GOLDEN FIXTURE, for logic that genuinely must run in both languages:
   ``web/lib/sean/fixtures/ledger.json`` is read by ``test_sean_ledger.py`` AND
   ``web/lib/sean/ledger.test.ts``, and both must reproduce it. That twin is fine as it stands.
3. A PYTHON TEST THAT READS THE TYPESCRIPT -- this file, modelled on
   ``test_lab_gate_wording.py``, which already scans shipped ``.ts`` for stale bar literals.

What is deliberately NOT done: a codegen step. Generating four constants would add a generator, a
drift check and a new CI failure mode to guard less than this file guards.

EVERY PARSE MUST FAIL LOUDLY. A regex that stops matching after a refactor would turn this file
into a test that passes by finding nothing, which is worse than no test: each helper asserts it
found its literal, and ``test_every_mirror_is_covered`` asserts the set of guarded names has not
quietly shrunk.
"""

from __future__ import annotations

import re
from decimal import Decimal

from seer_engine import config
from seer_engine.paper.capital import PAPER_INITIAL_IDR
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.model import initial_cash_usd
from seer_engine.sim.rules import PRESETS, RESIZE_BAND

CADENCE = "web/lib/cadence.ts"
REMINDERS = "web/lib/sean/reminders.ts"
CASH = "web/lib/sean/cash.ts"

#: Every mirrored name this file checks, and the file it lives in. Asserted complete below.
GUARDED: dict[str, str] = {
    "RESIZE_BAND": CADENCE,
    "RESIZING_RULES": REMINDERS,
    "OWNER_MONTHLY": CASH,
    "OWNER_USD_IDR": CASH,
}


def _src(rel: str) -> str:
    path = config.REPO_ROOT / rel
    assert path.exists(), f"{rel} is gone; a mirror guard must be moved, not silently skipped"
    return path.read_text(encoding="utf-8")


def _const(src: str, name: str, rel: str) -> Decimal:
    """The numeric literal of ``export const <name> = <number>;`` (TS numeric separators allowed)."""
    m = re.search(rf"export const {name}\s*(?::[^=]+)?=\s*([0-9][0-9_]*(?:\.[0-9_]+)?)\s*;", src)
    assert m is not None, f"{rel}: could not find `export const {name} = <number>`; fix this parse"
    return Decimal(m.group(1).replace("_", ""))


def _object_field(src: str, obj: str, field: str, rel: str) -> Decimal:
    """A numeric field of ``export const <obj>... = { ... };``."""
    block = re.search(rf"export const {obj}\s*(?::[^=]+)?=\s*\{{(.*?)\n\}};", src, re.S)
    assert block is not None, f"{rel}: could not find the `{obj}` object literal; fix this parse"
    m = re.search(rf"\b{field}\s*:\s*([0-9][0-9_]*(?:\.[0-9_]+)?)\s*,", block.group(1))
    assert m is not None, f"{rel}: `{obj}` has no numeric `{field}`; fix this parse"
    return Decimal(m.group(1).replace("_", ""))


def _string_array(src: str, name: str, rel: str) -> list[str]:
    block = re.search(rf"export const {name}\s*(?::[^=]+)?=\s*\[(.*?)\];", src, re.S)
    assert block is not None, f"{rel}: could not find the `{name}` array; fix this parse"
    found = re.findall(r"'([^']+)'", block.group(1))
    assert found, f"{rel}: `{name}` parsed as empty; fix this parse"
    return found


# --------------------------------------------------------------------------- the mirrors


def test_resize_band_matches_the_engine():
    assert _const(_src(CADENCE), "RESIZE_BAND", CADENCE) == RESIZE_BAND


def test_resizing_rules_are_exactly_the_book_presets_that_resize():
    """``reminders.resizes`` decides whether the owner is told to top a holding up each month.

    Miss a preset and a roster strategy silently stops producing add/trim reminders; invent one and
    the page asks for trades the engine never makes. The set is derived, never typed.
    """
    derived = {r.id for r in PRESETS if r.engine == "book" and r.resize}
    mirrored = _string_array(_src(REMINDERS), "RESIZING_RULES", REMINDERS)
    assert len(mirrored) == len(set(mirrored)), "RESIZING_RULES has a duplicate"
    assert set(mirrored) == derived, (
        f"RESIZING_RULES drifted: only in TS {sorted(set(mirrored) - derived)}, "
        f"only in the engine {sorted(derived - set(mirrored))}"
    )


def test_owner_monthly_matches_the_engines_schedule():
    """``cash.OWNER_MONTHLY`` drives the derived wallet, so a drift here misstates real money."""
    src = _src(CASH)
    assert _object_field(src, "OWNER_MONTHLY", "monthlyIdr", CASH) == OWNER_MONTHLY.amount_idr
    assert _object_field(src, "OWNER_MONTHLY", "dayOfMonth", CASH) == OWNER_MONTHLY.day_of_month
    # The opening deposit is the paper book's own starting capital, not a separate number.
    assert _object_field(src, "OWNER_MONTHLY", "initialIdr", CASH) == PAPER_INITIAL_IDR


def test_owner_usd_idr_still_converts_the_opening_deposit_to_its_documented_dollars():
    """``OWNER_USD_IDR`` is the fallback rate, and its docstring claims it is the rate the owner's
    real 10,000,000 IDR was converted at -- ``paper_state.initial_cash_usd = 560.5067``.

    There is no Python constant to compare it against, so the claim itself is the invariant: put
    the engine's own conversion over it and the documented figure must come back. Change the rate
    without changing the claim and this fails.
    """
    rate = _const(_src(CASH), "OWNER_USD_IDR", CASH)
    assert initial_cash_usd(Decimal(PAPER_INITIAL_IDR), rate) == Decimal("560.5067")


def test_every_mirror_is_covered():
    """The guarded set has not quietly shrunk, and each name is still in the file claimed."""
    assert set(GUARDED) == {"RESIZE_BAND", "RESIZING_RULES", "OWNER_MONTHLY", "OWNER_USD_IDR"}
    for name, rel in GUARDED.items():
        assert f"export const {name}" in _src(rel), f"{name} is no longer exported from {rel}"
