"""The P7a candidate registry (handover D6, §7.5; plan phase 11).

- Identity: unique, well-formed ids, at most ``MAX_CANDIDATES`` entries, the first 54 exactly the
  plan index's Registry table in order.
- Append only: ``PINS`` holds ``(id, candidate_digest)`` for every entry. Editing, reordering or
  removing a registered candidate changes a pinned digest and fails here. An append adds its pin
  line at the END of ``PINS`` in the same commit as the registry entry, before its dev run.
- Owner inputs: the declared ``owner_inputs`` equal ``dev.candidate_owner_inputs``, and the
  flagged set is exactly the planned one.
- Pairing: presets only (never ``V0_BOOK``), ``DESIGN_V0`` only with a bracket ``Strategy``, a
  ``"limit"`` entry only for families that price their entries, families match allocators.
- Smoke: every candidate runs a short window through ``dev.run_candidate`` on a synthetic market
  holding every fixed symbol the registry reads plus a few member stocks.

Re-pin (after an append only):
    engine/.venv/bin/python -c "from seer_engine.backtest.registry import REGISTRY, candidate_digest; [print(f'    ({c.id!r}, {candidate_digest(c)!r}),') for c in REGISTRY]"
and paste the NEW lines at the end of PINS. Existing lines are never changed.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pytest

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.book_runner import BookResult
from seer_engine.backtest.dev import (
    DEV_END,
    MAX_CANDIDATES,
    candidate_owner_inputs,
    candidate_window,
    run_candidate,
)
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.registry import (
    FIRST_APPEND,
    REGISTRY,
    SECTOR_ETFS,
    candidate_digest,
    candidate_text,
)
from seer_engine.backtest.runner import RunResult
from seer_engine.sim.rules import (
    DESIGN_V0,
    LEVERAGED_ETFS,
    PRESETS,
    SWING_T10,
    SWING_T20,
    SWING_T20_OPEN,
    V0_BOOK,
)
from seer_engine.strategies.allocator import BLEND, VOLTARGET, Allocator
from seer_engine.strategies.base import History, Strategy
from seer_engine.strategies.f_index import TimingParams

ID_RE = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)*$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
FAMILIES = frozenset({"REF", *(f"F{i}" for i in range(1, 12))})
SWING_PRESETS = (SWING_T10, SWING_T20, SWING_T20_OPEN)
# Leaf allocator ids allowed under rules.entry == "limit": F7 and PICKS price their entries; F1's
# limit-less targets are bought by the engine's open_limit fallback (plan index D-B, row 54's core).
PRICED_ENTRY_LEAVES = frozenset({"F1", "F7", "PICKS"})
# The leaf allocator id each catalogue family must use (F9 is a BLEND, REF is free).
FAMILY_LEAF = {
    "F1": "F1", "F10": "F1", "F11": "F11",
    "F2": "ROT", "F3": "ROT",
    "F4": "FAC", "F5": "FAC", "F6": "FAC",
    "F7": "F7",
}
FACTOR_RANK = {"F4": "momentum", "F5": "lowvol", "F6": "mom_lowvol"}

# The plan index's Registry table, rows 1-54, in order (id, family).
PLAN_ROWS: tuple[tuple[str, str], ...] = (
    ("REF-SPY-HOLD", "REF"),
    ("REF-A-V0", "REF"),
    ("F1-SPY-SMA200-D", "F1"),
    ("F1-SPY-SMA200-M", "F1"),
    ("F1-SPY-SMA100-D", "F1"),
    ("F1-SPY-SMA50-D", "F1"),
    ("F1-SPY-10MSMA-M", "F1"),
    ("F1-SPY-ABS12-M", "F1"),
    ("F1-SPY-SMA200-D-TBILL", "F1"),
    ("F1-QQQ-SMA200-D", "F1"),
    ("F1-QQQ-SMA200-M", "F1"),
    ("F1-QQQ-SMA100-D", "F1"),
    ("F1-QQQ-SPYSIG-D", "F1"),
    ("F1-QQQ-10MSMA-M", "F1"),
    ("F1-SPY-VT12-W", "F1"),
    ("F1-QQQ-VT15-W", "F1"),
    ("F10-SSO-SMA200-D", "F10"),
    ("F10-QLD-SMA200-D", "F10"),
    ("F10-SSO-10MSMA-M", "F10"),
    ("F11-SPY-TOM", "F11"),
    ("F11-SPY-TOM-TREND", "F11"),
    ("F11-QQQ-TOM-TREND", "F11"),
    ("F2-SPYQQQ-12M", "F2"),
    ("F2-SPYQQQ-6M", "F2"),
    ("F2-SPYQQQ-3M", "F2"),
    ("F2-SPYQQQ-12M-IEF", "F2"),
    ("F2-GEM-SPYEFA-IEF", "F2"),
    ("F3-SEC-TOP3-6M", "F3"),
    ("F3-SEC-TOP3-12M", "F3"),
    ("F3-SEC-TOP2-3M", "F3"),
    ("F3-SEC-TOP3-6M-TREND", "F3"),
    ("F3-SEC-TOP3-6M-IEF", "F3"),
    ("F4-MOM12-N10", "F4"),
    ("F4-MOM12-N10-TREND", "F4"),
    ("F4-MOM12-N20-TREND", "F4"),
    ("F4-MOM12-N5-TREND", "F4"),
    ("F4-MOM6-N10-TREND", "F4"),
    ("F4-MOM12-N10-TREND-IVOL", "F4"),
    ("F4-MOM12-N10-TREND-W", "F4"),
    ("F5-LV60-N20", "F5"),
    ("F5-LV60-N20-TREND", "F5"),
    ("F5-LV252-N20-TREND", "F5"),
    ("F6-ML-P50-N10-TREND", "F6"),
    ("F6-ML-P50-N20-TREND", "F6"),
    ("F6-ML-P50-N10-VT12", "F6"),
    ("F7-RSI2-T20-DIP", "F7"),
    ("F7-RSI2-T10-DIP", "F7"),
    ("F7-RSI2-T20-CLOSE", "F7"),
    ("F7-RSI2-T20-OPEN", "F7"),
    ("F7-RSI2-T20-N8", "F7"),
    ("F7-RSI2-T20-TREND", "F7"),
    ("F7-RSI2-T20-NOSTOP", "F7"),
    ("F9-SPY200M70-MOM30", "F9"),
    ("F9-SPY200D50-SWING50", "F9"),
)

_SECTOR_FLAGS = tuple(f"etf:{s}" for s in SECTOR_ETFS)
# Every candidate that needs owner verification, and exactly what it needs (handover "Owner inputs").
FLAGGED: dict[str, tuple[str, ...]] = {
    "F1-SPY-SMA200-D-TBILL": ("etf:BIL",),
    "F10-SSO-SMA200-D": ("etf:SSO", "leverage"),
    "F10-QLD-SMA200-D": ("etf:QLD", "leverage"),
    "F10-SSO-10MSMA-M": ("etf:SSO", "leverage"),
    "F2-SPYQQQ-12M-IEF": ("etf:IEF",),
    "F2-GEM-SPYEFA-IEF": ("etf:EFA", "etf:IEF"),
    "F3-SEC-TOP3-6M": _SECTOR_FLAGS,
    "F3-SEC-TOP3-12M": _SECTOR_FLAGS,
    "F3-SEC-TOP2-3M": _SECTOR_FLAGS,
    "F3-SEC-TOP3-6M-TREND": _SECTOR_FLAGS,
    "F3-SEC-TOP3-6M-IEF": ("etf:IEF",) + _SECTOR_FLAGS,
}

# (id, candidate_digest) for every registered candidate, in registry order. APPEND ONLY.
PINS: tuple[tuple[str, str], ...] = (
    ('REF-SPY-HOLD', '5af78e87c19f576eb0b7feef58343678896b8507787ca7ded81cf1363ac72840'),
    ('REF-A-V0', '0f041facd0736aeaaf00726b4d74191f7126ca742f09ed66b0ee4b66948ef599'),
    ('F1-SPY-SMA200-D', 'e7bc1f6e6d0f9367873c4e57bf55902146e71fbafd25c5f0a14e50b75e65f137'),
    ('F1-SPY-SMA200-M', 'c5b0362555d5ec6dacdffd79f9c3020d1de31e55d2c0aec2e96730935d45aeee'),
    ('F1-SPY-SMA100-D', 'acfc1886322ebb8eae4d89c3360402d80f998c060ea2091709a31ca59efbbf34'),
    ('F1-SPY-SMA50-D', 'bc3977d8ea5f4e578b82943b6a34b72de83ed6de733171880c14c02e7a320d04'),
    ('F1-SPY-10MSMA-M', '4bd78a1c807dae0daa4ab14bda9057155efc0c9e0d51fbbdd047a4812f22f6c5'),
    ('F1-SPY-ABS12-M', '538ff597669dadf47f5e62b0ca08602c54b98a5936786a1aafae615acc77e372'),
    ('F1-SPY-SMA200-D-TBILL', '0b913846966cc01d840addaadb77ced1eb7e01c0126fd79a0c74a54d64a2a06a'),
    ('F1-QQQ-SMA200-D', '344f148da4d1a2b5f43b9fecc4600115b3b4dbcc7e77bad8bf3307edd30d1c8a'),
    ('F1-QQQ-SMA200-M', 'd864bbfe08e6eccb3c3f521c9bdd06ee2a1f0c41f35ac6d3a4f49fa38f24aebb'),
    ('F1-QQQ-SMA100-D', 'c982d37009a880f3c9c0978a83ec03a79daf15fbb07046f2ae74e5150de5bbf3'),
    ('F1-QQQ-SPYSIG-D', '89e6cc7f4252a8bdfd30d365f32246499ee7a95aec0b11c556234f2c588b1515'),
    ('F1-QQQ-10MSMA-M', 'ee263ba800581fc45e57dbb87e1640587ac97caa3fcdc19532cb58f71d7d58fa'),
    ('F1-SPY-VT12-W', '5f956207399bd70bdb643b1d2a67f5345a8087fb42ec909d3e443444b0c65f42'),
    ('F1-QQQ-VT15-W', 'bdffbd5cd5300f8032cec904a799aa38f148c5cf46ee3f741737e908229be516'),
    ('F10-SSO-SMA200-D', '495233ff6820fa41ab8c93eee9a4f62047cb2c34151dd48f41f838739a4c570c'),
    ('F10-QLD-SMA200-D', '3660f13bc0b5c5494f01624284fa4b4a0a1967214cdbec218656a8375ccafbe5'),
    ('F10-SSO-10MSMA-M', '2fa6a5f8c311fd56925fae1acc8b4f15f5c9908d245db73fec20e937f752a66c'),
    ('F11-SPY-TOM', '0f9632415186e6c09c1875e1bff4d2b90595a954ea062990508f6460aee7d95d'),
    ('F11-SPY-TOM-TREND', 'f95154748b5acac108f6fda56c65f637acf5ea785b4ba140b0758f507b86924d'),
    ('F11-QQQ-TOM-TREND', '5e7bef24c1429988850663aa2d7dba50315e48a0df856fcdc57dc8fdb30d4ec3'),
    ('F2-SPYQQQ-12M', '56362db475cb6640f694ffdd41aafa354e3b64fbe6a45686420bb8bea7bc2554'),
    ('F2-SPYQQQ-6M', '115357d108ff2107ea005bda8477ba58bbe3aff17d5e863f626b65ca1816894d'),
    ('F2-SPYQQQ-3M', '867c08d685c60820232812809f03f94f98ebbd51c1a5b4956ac5044a44b93456'),
    ('F2-SPYQQQ-12M-IEF', 'dae1b59922079836c6e9a5e4123a665bd4f957ccc5c3214a6a6ecb8a131e4f86'),
    ('F2-GEM-SPYEFA-IEF', '43250960d757b2ad7921d0afa01c474774656c83da91722340e2b8992308c9ef'),
    ('F3-SEC-TOP3-6M', '0c1275ef95addad927bfa58e4c80fe05dfb0b61c3c6306cd182993e8dd8dd8b1'),
    ('F3-SEC-TOP3-12M', '8a9d75542df284c05541b707437546ee9437fc6cb066793d1d1a8810ed92d73f'),
    ('F3-SEC-TOP2-3M', 'bde56322f7547ae57ed5b4289a678de1bebdc25cf5143a323cc487b03f9c9d5f'),
    ('F3-SEC-TOP3-6M-TREND', 'a2a43e7d89938bdaf77363ec7beb9e56e3bafbc4d9f55f0dc5f033b5e27d7110'),
    ('F3-SEC-TOP3-6M-IEF', '88c5ff3d039e5a71c0f9c8e864a86a54dfdf0bbdc33c95c188df8eb46651b01c'),
    ('F4-MOM12-N10', '3ae149c01637da59b943239c682712b6080181f1b189d63da95c3bc9f6ea415d'),
    ('F4-MOM12-N10-TREND', '2b13bcf9d7e1c79f2aac596afac78826d51b89580e900b2b36a5e9a5a57432f8'),
    ('F4-MOM12-N20-TREND', '9ddaf6083d571a34ab232d37177d2dc96e3a25f23548fdb16c16ae0f31a37791'),
    ('F4-MOM12-N5-TREND', 'ea6bc3877c26ba1ff88048de2159945bcc45caca9cd85154b3c5e2a5bf4a8a4f'),
    ('F4-MOM6-N10-TREND', 'ecb93aefdb1950539ab36ce5d886c3e0dafb7073ce0101f7fbae2ccb98b9d32a'),
    ('F4-MOM12-N10-TREND-IVOL', 'f5f86105d4323dde6fa65fc9399a47cd5f7227f38277ee929162d76f8b0fcc44'),
    ('F4-MOM12-N10-TREND-W', '1ffdfe0c4c5207c7b775b942e5c89620dbd262582bcf6f7008d44300bc2bdb0f'),
    ('F5-LV60-N20', '74e6e48497ae882a57a0bc3536c920c6c56dd63ff8961326476eb64fcc9bc7ef'),
    ('F5-LV60-N20-TREND', '92aa06dcafd99299a441e93465fa73a89bafdcc65dc9d8081fbecaa674d02e70'),
    ('F5-LV252-N20-TREND', '4624547277a85e821e9d673f6485ccd6b16598d44fa641c4e594ecc9df23a2f2'),
    ('F6-ML-P50-N10-TREND', 'f7add877264a09b867bc5a8b80e93c1356ecd26c45a323245a6507007fed055b'),
    ('F6-ML-P50-N20-TREND', '0a6059f14df10a8f254260210375be138c6e4d0208891bc2d9a63bb41963e600'),
    ('F6-ML-P50-N10-VT12', '27825dd3496b0ff285d3d0fc002e8f7a059a1f8017944a86c06941b1a0abedf6'),
    ('F7-RSI2-T20-DIP', '21afdf9016b00953980b9c926ad311e9220d84edbdb4df3d208fb80d7b5d5698'),
    ('F7-RSI2-T10-DIP', '7ce0511225d9831cbdaa54890c9178caa434ee3e9c159564d377370658e72754'),
    ('F7-RSI2-T20-CLOSE', '808b0f2fc8b8c92345bef4b1654424886890b1019f21fd24657dce1190f87577'),
    ('F7-RSI2-T20-OPEN', '0b3ed507d3244409e299a32e92363fa3620273d5efdf8a146161b99be610ebf7'),
    ('F7-RSI2-T20-N8', '32ccaaf8ba7e45952d808928002fbda4d2cef07618de37a3ae6b59e30e5aca92'),
    ('F7-RSI2-T20-TREND', '54f4fabb2ada158f482b83a518f7ebba1cd49cbf1fa4d7b0a2734fe1a2c529da'),
    ('F7-RSI2-T20-NOSTOP', '962b71cd74ffa1bf88c6f33d2ff73d854182b713519f162dc9675d1a1097b2d3'),
    ('F9-SPY200M70-MOM30', '18a8da6a9a6e7f867882e2a351eca11d21fdabcb625ec70e2f14e18eee58898a'),
    ('F9-SPY200D50-SWING50', '1bc8023e58a7f0c1cffb111a3b81aa0e574fcd5adbc6c4da96407e55a250690b'),
)


def _by_id(cid: str):
    return next(c for c in REGISTRY if c.id == cid)


def _leaves(allocator: Any, params: Any) -> list[tuple[Any, Any]]:
    """The (allocator, params) leaves under BLEND and VOLTARGET overlays, in part order."""
    if allocator is BLEND:
        out: list[tuple[Any, Any]] = []
        for part in params.parts:
            out += _leaves(part.allocator, part.params)
        return out
    if allocator is VOLTARGET:
        return _leaves(params.inner, params.inner_params)
    return [(allocator, params)]


# ---- identity -------------------------------------------------------------------------------


def test_ids_are_unique_and_well_formed():
    ids = [c.id for c in REGISTRY]
    assert len(ids) == len(set(ids))
    assert all(ID_RE.match(i) for i in ids), [i for i in ids if not ID_RE.match(i)]


def test_registry_size_is_within_the_cap():
    assert MAX_CANDIDATES == 60
    assert 54 <= len(REGISTRY) <= MAX_CANDIDATES


def test_first_54_are_the_plan_index_table_in_order():
    assert tuple((c.id, c.family) for c in REGISTRY[:54]) == PLAN_ROWS


def test_families_are_catalogue_labels_and_prefix_the_id():
    for c in REGISTRY:
        assert c.family in FAMILIES, c.id
        assert c.id.startswith(c.family + "-"), c.id


def test_rationales_are_one_non_empty_line():
    for c in REGISTRY:
        assert isinstance(c.rationale, str) and c.rationale.strip() == c.rationale, c.id
        assert c.rationale and "\n" not in c.rationale, c.id


def test_added_dates_are_append_ordered():
    assert all(c.added == FIRST_APPEND for c in REGISTRY[:54])
    assert FIRST_APPEND >= date(2026, 10, 3)  # never before the handover that defines it
    added = [c.added for c in REGISTRY]
    assert added == sorted(added)
    assert added[-1] <= date.today()


# ---- append only ----------------------------------------------------------------------------


def test_pins_are_real_digests():
    assert len({i for i, _ in PINS}) == len(PINS)
    bad = [i for i, d in PINS if not HEX64_RE.match(d)]
    assert bad == [], f"unpinned: {bad} (run the re-pin command in this file's docstring)"


def test_registry_is_append_only_against_the_pins():
    assert len(REGISTRY) >= len(PINS), "a pinned candidate was removed"
    current = tuple((c.id, candidate_digest(c)) for c in REGISTRY[: len(PINS)])
    changed = [p[0] for p, c in zip(PINS, current) if p != c]
    assert changed == [], f"pinned candidates changed or moved: {changed}"


def test_every_entry_is_pinned():
    assert len(PINS) == len(REGISTRY), "an appended candidate has no pin line yet"


def test_candidate_text_format():
    text = candidate_text(REGISTRY[0])
    assert text.startswith("id=REF-SPY-HOLD\nfamily=REF\nrules=TradeRules(id='monthly-hold',engine='book',")
    assert text.endswith(
        "\nallocator=<F1>\nparams=TimingParams(hold='SPY',signal='SPY',rule='always',n=1)\n"
    )
    assert "cost_rate=0.001" in text
    assert candidate_text(_by_id("REF-A-V0")).splitlines()[3] == "allocator=<A>"
    blend = candidate_text(_by_id("F9-SPY200M70-MOM30"))
    assert "params=BlendParams(parts=(BlendPart(allocator=<F1>," in blend
    assert "share=0.7)" in blend and "share=0.3)" in blend


def test_digest_covers_the_trial_and_ignores_the_prose():
    c = _by_id("F1-SPY-SMA200-D")
    d = candidate_digest(c)
    assert HEX64_RE.match(d)
    assert candidate_digest(replace(c)) == d
    assert candidate_digest(replace(c, rationale="different words")) == d
    assert candidate_digest(replace(c, added=date(2030, 1, 1))) == d
    assert candidate_digest(replace(c, params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=201))) != d
    assert candidate_digest(replace(c, rules=_by_id("F1-SPY-SMA200-M").rules)) != d
    assert candidate_digest(replace(c, id="F1-SPY-SMA200-X")) != d
    assert len({candidate_digest(x) for x in REGISTRY}) == len(REGISTRY)


# ---- owner inputs ---------------------------------------------------------------------------


def test_declared_owner_inputs_match_the_computed_ones():
    wrong = [(c.id, c.owner_inputs, candidate_owner_inputs(c))
             for c in REGISTRY if c.owner_inputs != candidate_owner_inputs(c)]
    assert wrong == []


def test_flagged_candidates_are_exactly_the_planned_ones():
    flagged = {c.id: c.owner_inputs for c in REGISTRY[:54] if c.owner_inputs}
    assert flagged == FLAGGED
    assert sum(1 for c in REGISTRY[:54] if not c.owner_inputs) == 43


# ---- rules / allocator pairing -------------------------------------------------------------


def test_rules_are_registry_presets_never_v0_book():
    for c in REGISTRY:
        assert any(c.rules is p for p in PRESETS), c.id
        assert c.rules is not V0_BOOK, c.id


def test_design_v0_only_with_a_bracket_strategy():
    for c in REGISTRY:
        is_strategy = isinstance(c.allocator, Strategy) and not isinstance(c.allocator, Allocator)
        assert (c.rules is DESIGN_V0) == is_strategy, c.id
        if c.rules is not DESIGN_V0:
            assert c.rules.engine == "book" and isinstance(c.allocator, Allocator), c.id


def test_limit_entry_only_for_families_that_price_their_entries():
    for c in REGISTRY:
        if c.rules is DESIGN_V0 or c.rules.entry != "limit":
            continue
        ids = {a.id for a, _ in _leaves(c.allocator, c.params)}
        assert ids <= PRICED_ENTRY_LEAVES, (c.id, ids)


def test_swing_rules_go_with_the_swing_family():
    for c in REGISTRY:
        if c.rules is DESIGN_V0:
            continue
        ids = {a.id for a, _ in _leaves(c.allocator, c.params)}
        if c.family == "F7":
            assert any(c.rules is r for r in SWING_PRESETS), c.id
            assert c.rules.time_stop is not None and c.rules.idle_symbol is None, c.id
        if any(c.rules is r for r in SWING_PRESETS):
            assert "F7" in ids, c.id


def test_family_matches_its_allocators():
    for c in REGISTRY:
        if c.family == "REF":
            continue
        if c.family == "F9":
            assert c.allocator is BLEND and len(c.params.parts) >= 2, c.id
            continue
        leaves = _leaves(c.allocator, c.params)
        assert {a.id for a, _ in leaves} == {FAMILY_LEAF[c.family]}, c.id
        for a, p in leaves:
            held = set(a.holds(p))
            if c.family in FACTOR_RANK:
                assert p.rank == FACTOR_RANK[c.family], c.id
            if c.family == "F1":
                assert not held & LEVERAGED_ETFS, c.id
            if c.family == "F10":
                assert held & LEVERAGED_ETFS, c.id
            if c.family == "F2":
                assert set(p.universe) <= {"EFA", "QQQ", "SPY"}, c.id
            if c.family == "F3":
                assert p.universe == SECTOR_ETFS, c.id


def test_sector_etfs():
    assert SECTOR_ETFS == tuple(sorted(SECTOR_ETFS))
    assert SECTOR_ETFS == ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")


# ---- smoke: every candidate runs on a synthetic market --------------------------------------

SMOKE_FIRST = date(2013, 12, 2)  # 473 NYSE sessions through DEV_END: lookbacks up to ~400 fit
FIXED_SYMBOLS: tuple[str, ...] = tuple(sorted(
    {"BIL", "EFA", "IEF", "QLD", "QQQ", "SPY", "SSO", *SECTOR_ETFS}
))
MEMBER_STOCKS: tuple[str, ...] = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH")
SPY_EX_DATE = date(2015, 6, 19)
SMOKE_DIVIDENDS: dict[str, dict[date, Decimal]] = {
    "SPY": {SPY_EX_DATE: Decimal("1.0300")},
    "AAA": {date(2015, 3, 13): Decimal("0.2500")},
}
SMOKE_SPY_DIVIDENDS: tuple[Dividend, ...] = (Dividend(SPY_EX_DATE, Decimal("1.0300")),)


def _smoke_history(symbol: str, k: int, days: list[date]) -> History:
    """A deterministic, positive, 2-dp price path: drift + a slow wave + a down day in three
    (RSI(2) dips) + a market-wide ~25% dip around session 380 (trend filters switch off)."""
    n = len(days)
    t = np.arange(n, dtype=np.float64)
    base = 40.0 + 7.0 * k
    drift = 0.0009 - 0.0004 * (k % 4)
    wave = 1.0 + 0.07 * np.sin(2.0 * np.pi * t / (60.0 + 11.0 * k) + k)
    zig = np.where(t % 3 == 0, 0.985, 1.006)
    shock = 1.0 - 0.25 * np.exp(-(((t - 380.0) / 25.0) ** 2))
    close = np.round(base * (1.0 + drift * t) * wave * zig * shock, 2)
    open_ = np.round(np.concatenate((close[:1], close[:-1])), 2)
    high = np.round(np.maximum(open_, close) * 1.01, 2)
    low = np.round(np.minimum(open_, close) * 0.99, 2)
    volume = np.full(n, 2_000_000.0, dtype=np.float64)
    return History(symbol, np.array(days, dtype="datetime64[D]"), open_, high, low, close, volume)


@pytest.fixture(scope="module")
def smoke_market() -> Market:
    days = dates.sessions(SMOKE_FIRST, DEV_END)
    symbols = FIXED_SYMBOLS + MEMBER_STOCKS
    history = {s: _smoke_history(s, k, days) for k, s in enumerate(symbols)}
    membership = Membership(intervals=tuple((s, days[0], None) for s in MEMBER_STOCKS))
    return Market(history=history, membership=membership, fx=((days[0], Decimal("2000")),))


def test_smoke_market_covers_every_fixed_symbol(smoke_market):
    for c in REGISTRY:
        if c.rules is DESIGN_V0:
            continue
        needed = set(c.allocator.symbols(c.params)) | set(c.allocator.holds(c.params))
        if c.rules.idle_symbol is not None:
            needed.add(c.rules.idle_symbol)
        assert needed <= set(FIXED_SYMBOLS), (c.id, sorted(needed - set(FIXED_SYMBOLS)))
        assert needed <= set(smoke_market.history), c.id


@pytest.mark.parametrize("c", REGISTRY, ids=[c.id for c in REGISTRY])
def test_every_candidate_runs_a_smoke_window(smoke_market, c):
    result, row = run_candidate(smoke_market, SMOKE_DIVIDENDS, SMOKE_SPY_DIVIDENDS, c)
    start, end = candidate_window(smoke_market, c)
    window = dates.sessions(start, end)
    assert row.candidate == c
    assert (row.start, row.end) == (start, end)
    assert end == DEV_END
    assert len(window) >= 20, f"{c.id}: smoke window only {len(window)} sessions; lookback too long for the synthetic market"
    assert len(result.snapshots) == len(window) + 1
    assert result.snapshots[-1].date == DEV_END
    if c.rules is DESIGN_V0:
        assert isinstance(result, RunResult)
    else:
        assert isinstance(result, BookResult)
