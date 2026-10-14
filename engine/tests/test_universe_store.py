"""The dollar-volume universe store builder."""

from __future__ import annotations

from datetime import date

import pytest

from seer_engine import research
from seer_engine.commands import universe_store as us

D = date


def test_the_new_purpose_is_allowed_and_distinct():
    """A store the lab must refuse to record trials against needs a mark `_seal` accepts."""
    assert research.UNIVERSE_PURPOSE == "dollar-volume-universe"
    assert research.UNIVERSE_PURPOSE in research.PURPOSES
    assert research.UNIVERSE_PURPOSE != research.SURVIVORSHIP_PURPOSE


def test_the_band_parses_inclusively():
    assert us._band("1-2000") == (1, 2000)
    assert us._band("500-1000") == (500, 1000)


def test_a_missing_rank_file_refuses_before_touching_the_cache(tmp_path):
    with pytest.raises(us.UniverseStoreError) as e:
        us.plan_build(tmp_path, tmp_path / "absent.csv", (1, 2000))
    assert "month-end rank CSV" in str(e.value)


def test_a_missing_cache_refuses(tmp_path):
    ranks = tmp_path / "r.csv"
    ranks.write_text("sample_date,traded_date,code,close,volume,dollar_volume,rank\n", encoding="utf-8")
    with pytest.raises(us.UniverseStoreError) as e:
        us.plan_build(tmp_path / "nocache", ranks, (1, 2000))
    assert "universe pull" in str(e.value)


def _fixture(tmp_path, codes):
    ranks = tmp_path / "r.csv"
    rows = ["sample_date,traded_date,code,close,volume,dollar_volume,rank"]
    for i, c in enumerate(codes, 1):
        rows.append(f"1998-01-31,1998-01-30,{c},10,100,1000,{i}")
    ranks.write_text("\n".join(rows) + "\n", encoding="utf-8")
    cache = tmp_path / "cache"
    (cache / "eod").mkdir(parents=True)
    for c in codes:
        (cache / "eod" / f"{c}.json").write_text("null\n", encoding="utf-8")
    return cache, ranks


def test_a_cache_without_the_benchmark_refuses_and_says_why(tmp_path):
    """A store with no SPY has no benchmark, so the lab could score nothing on it. Refusing at
    plan time costs seconds; discovering it after an hour of cleaning does not."""
    cache, ranks = _fixture(tmp_path, ["AAA", "BBB"])
    with pytest.raises(us.UniverseStoreError) as e:
        us.plan_build(cache, ranks, (1, 2000))
    msg = str(e.value)
    assert "SPY" in msg and "benchmark" in msg


def test_the_etfs_join_the_symbol_set_even_though_nothing_ranks_them(tmp_path):
    cache, ranks = _fixture(tmp_path, ["AAA", *research.RESEARCH_ETFS])
    plan = us.plan_build(cache, ranks, (1, 2000))
    assert set(research.RESEARCH_ETFS) <= set(plan.symbols)
    assert "AAA" in plan.symbols
    assert plan.band == (1, 2000)


def test_an_etf_is_a_member_for_the_whole_window_and_a_ranked_name_is_not(tmp_path):
    cache, ranks = _fixture(tmp_path, ["AAA", *research.RESEARCH_ETFS])
    plan = us.plan_build(cache, ranks, (1, 2000))
    window = [d for d in plan.sessions if d >= us.UNIVERSE_START]
    assert len(us._member_days(plan, "SPY", window)) == len(window)
    ranked = us._member_days(plan, "AAA", window)
    assert 0 < len(ranked) <= len(window)
    assert min(ranked) >= us.UNIVERSE_START


def test_the_limit_only_trims_ranked_names_never_the_etfs(tmp_path):
    cache, ranks = _fixture(tmp_path, [f"S{i}" for i in range(30)] + list(research.RESEARCH_ETFS))
    plan = us.plan_build(cache, ranks, (1, 2000), limit=5)
    assert set(research.RESEARCH_ETFS) <= set(plan.symbols)
    assert len([s for s in plan.symbols if s not in research.RESEARCH_ETFS]) == 5
