"""Per-pick evidence (why-this-pick-pipeline phase 1; requirements R1, R8).

Every roster object except the benchmark has an evidence function; each one returns distinct,
plain-English facts per symbol, built only from bars dated on or before the data date (and
filings filed on or before it), with no indicator codes or ids. The purity scan in
tests/test_strategy_purity.py covers ``strategies/evidence.py`` through its glob.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date, timedelta
from itertools import combinations
from pathlib import Path

import pytest
from stratkit import dip, hist, mutate_from, session_days, uptrend

import seer_engine
from seer_engine import dates
from seer_engine.backtest.market import Market, Membership
from seer_engine.fundamentals import Fact, FundamentalPanel
from seer_engine.paper import roster
from seer_engine.strategies import evidence
from seer_engine.strategies.a import STRATEGY_A_PARAMS
from seer_engine.strategies.base import History
from seer_engine.strategies.c import STRATEGY_C_PARAMS
from seer_engine.strategies.f_factor import FactorParams
from seer_engine.strategies.f_fundamental import FundamentalParams
from seer_engine.strategies.f_index import TimingParams

F4 = roster.entry(roster.F4_ID).params
F1 = roster.entry(roster.F1_ID).params
FND = roster.FUNDAMENTAL_PARAMS

# Indicator codes, object names, ids and non-numbers the owner must never see (R8).
FORBIDDEN = re.compile(
    r"RSI|SMA|ATR|12-1|z-score|\bsue\b|SUE|STRATEGY|FACTOR|TIMING|FUNDAMENTAL|\bFAC\b|\bFND\b|"
    r"\bF\d+\b|C-news-veto|buy_and_hold|\bnan\b|\binf\b|None|_|"
    # advice or prediction words: Explain (phase 3) rejects a note that repeats one (its BANNED list),
    # and the site shows facts verbatim when there is no note (design §1, plan invariant 6)
    r"(?i:\bbuy(?:s|ing)?\b|\bsell(?:s|ing)?\b|\brecommend|\bshould|\bwill\b|\bgoing\s+to\b|\bexpect|\bguarantee)"
)


def market_of(history: dict[str, History], start: date, panel: FundamentalPanel | None = None) -> Market:
    """A Market where every symbol is a member from ``start`` on."""
    m = Market(
        history=history,
        membership=Membership(intervals=tuple((s, start, None) for s in sorted(history))),
        fx=(),
    )
    return m if panel is None else m.with_fundamentals(panel)


def assert_plain(out: dict[str, tuple[str, ...]]) -> None:
    """Every result is 2-6 one-line sentences with no code, id or non-number in them."""
    assert out, "the check must not be vacuous"
    for symbol, facts in out.items():
        assert isinstance(facts, tuple) and 2 <= len(facts) <= evidence.MAX_FACTS, (symbol, facts)
        for fact in facts:
            assert isinstance(fact, str) and fact.endswith("."), fact
            assert "\n" not in fact
            assert not FORBIDDEN.search(fact), fact


def assert_distinct(out: dict[str, tuple[str, ...]]) -> None:
    assert len(out) >= 2
    for a, b in combinations(out, 2):
        assert out[a] != out[b], (a, b)


def later_bars_changed(history: dict[str, History], data_date: date) -> dict[str, History]:
    """Every bar dated after ``data_date`` replaced by wild values (as if the future were different)."""
    return {s: mutate_from(h, dates.next_session(data_date)) for s, h in history.items()}


def cut_at(history: dict[str, History], data_date: date) -> dict[str, History]:
    return {s: h.upto(data_date) for s, h in history.items()}


# --------------------------------------------------------------------------- the table


def test_every_roster_object_but_the_benchmark_has_evidence():
    assert set(evidence.EVIDENCE) == set(roster.RESOLVER) - {roster.BENCHMARK_OBJECT}
    for name in evidence.EVIDENCE:
        assert evidence.has_evidence(name)
    assert not evidence.has_evidence(roster.BENCHMARK_OBJECT)
    assert not evidence.has_evidence("NO_SUCH_OBJECT")
    assert not evidence.has_evidence(None)  # type: ignore[arg-type]


def test_an_unknown_object_is_a_key_error():
    with pytest.raises(KeyError):
        evidence.evidence_for("NO_SUCH_OBJECT", None, None, date(2026, 10, 6), ["AAA"])  # type: ignore[arg-type]


def test_the_module_does_not_import_the_roster():
    """paper/roster.py imports strategies; evidence must load without it (no import cycle)."""
    pkg = Path(seer_engine.__file__).resolve().parent.parent
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pkg) + os.pathsep + env.get("PYTHONPATH", "")
    code = (
        "import sys\n"
        "import seer_engine.strategies.evidence\n"
        "print('seer_engine.paper.roster' in sys.modules)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True, timeout=120)
    assert out.stdout.strip() == "False"


def test_bad_inputs_raise():
    m = market_of({"AAA": hist("AAA", uptrend(10))}, session_days(1)[0])
    d = session_days(10)[-1]
    with pytest.raises(TypeError):
        evidence.evidence_for("STRATEGY_A", m, F4, d, ["AAA"])
    with pytest.raises(TypeError):
        evidence.evidence_for("STRATEGY_C", m, STRATEGY_A_PARAMS, d, ["AAA"])
    with pytest.raises(TypeError):
        evidence.evidence_for("FACTOR", m, F1, d, ["AAA"])
    with pytest.raises(TypeError):
        evidence.evidence_for("TIMING", m, F4, d, ["AAA"])
    with pytest.raises(TypeError):
        evidence.evidence_for("FUNDAMENTAL", m, F4, d, ["AAA"])
    with pytest.raises(TypeError):
        evidence.evidence_for("STRATEGY_A", m, STRATEGY_A_PARAMS, d, "AAA")


# --------------------------------------------------------------------------- Strategy A and C

A_DAYS = session_days(260)
A_DATE = A_DAYS[250]  # 9 sessions of later bars follow it


def a_history() -> dict[str, History]:
    """Three steady risers that dip sharply on A_DATE (they pass A's rule), one that does not."""
    out: dict[str, History] = {}
    for k, (symbol, drop) in enumerate((("AAA", 1.0), ("BBB", 2.0), ("CCC", 3.0))):
        closes = dip(uptrend(len(A_DAYS), first=100.0 + 50.0 * k), at=250, drop=drop)
        out[symbol] = hist(symbol, closes, days=A_DAYS)
    out["DDD"] = hist("DDD", uptrend(len(A_DAYS), first=80.0), days=A_DAYS)
    out["SPY"] = hist("SPY", uptrend(len(A_DAYS), first=400.0), days=A_DAYS, volume=50_000_000.0)
    return out


@pytest.fixture(scope="module")
def a_market() -> Market:
    return market_of(a_history(), A_DAYS[0])


def test_strategy_a_facts(a_market):
    out = evidence.evidence_for("STRATEGY_A", a_market, STRATEGY_A_PARAMS, A_DATE, ["AAA", "BBB", "CCC", "DDD", "ZZZ"])
    assert set(out) == {"AAA", "BBB", "CCC", "DDD"}  # ZZZ has no bars: absent, not empty
    assert_plain(out)
    assert_distinct(out)
    for symbol in ("AAA", "BBB", "CCC"):
        facts = out[symbol]
        assert len(facts) == 5
        assert facts[0].startswith("It closed at $") and "above its 200-day average of $" in facts[0]
        assert "2-day strength score was" in facts[1] and "below 10 counts as a sharp short drop" in facts[1]
        assert "Over the last 2 trading days it fell" in facts[2]
        assert "changed hands" in facts[3] and "million" in facts[3]
        assert " of 3 stocks that passed the rule" in facts[4]
    ranks = sorted(out[s][4].split()[2] for s in ("AAA", "BBB", "CCC"))
    assert ranks == ["1st", "2nd", "3rd"]
    assert len(out["DDD"]) == 4  # eligible but did not pass: no place in the ranking


def test_strategy_c_is_a_under_its_own_a_params(a_market):
    symbols = ["AAA", "BBB", "CCC"]
    c = evidence.evidence_for("STRATEGY_C", a_market, STRATEGY_C_PARAMS, A_DATE, symbols)
    a = evidence.evidence_for("STRATEGY_A", a_market, STRATEGY_C_PARAMS.a, A_DATE, symbols)
    assert c == a and c


def test_strategy_a_reads_nothing_after_the_data_date():
    h = a_history()
    symbols = sorted(h)
    base = evidence.evidence_for("STRATEGY_A", market_of(cut_at(h, A_DATE), A_DAYS[0]), STRATEGY_A_PARAMS, A_DATE, symbols)
    wild = evidence.evidence_for("STRATEGY_A", market_of(later_bars_changed(h, A_DATE), A_DAYS[0]), STRATEGY_A_PARAMS, A_DATE, symbols)
    full = evidence.evidence_for("STRATEGY_A", market_of(h, A_DAYS[0]), STRATEGY_A_PARAMS, A_DATE, symbols)
    assert base == wild == full and base


def test_a_non_member_is_absent():
    h = a_history()
    m = Market(
        history=h,
        membership=Membership(intervals=tuple((s, A_DAYS[0], None) for s in sorted(h) if s != "BBB")),
        fx=(),
    )
    out = evidence.evidence_for("STRATEGY_A", m, STRATEGY_A_PARAMS, A_DATE, ["AAA", "BBB"])
    assert set(out) == {"AAA"}
    assert " of 2 stocks that passed the rule" in out["AAA"][4]


# --------------------------------------------------------------------------- FACTOR (F4)

F_DAYS = session_days(320)
F_DATE = F_DAYS[310]


def factor_history() -> dict[str, History]:
    """Five liquid names rising at different speeds, plus SPY above its 200-day average."""
    out: dict[str, History] = {}
    for k, symbol in enumerate(("AAA", "BBB", "CCC", "DDD", "EEE")):
        closes = [50.0 * (1.0 + 0.0004 * (k + 1)) ** t + (0.3 if t % 2 else -0.3) for t in range(len(F_DAYS))]
        out[symbol] = hist(symbol, closes, days=F_DAYS, volume=2_000_000.0)
    out["SPY"] = hist("SPY", uptrend(len(F_DAYS), first=400.0, step=0.5), days=F_DAYS, volume=50_000_000.0)
    return out


@pytest.fixture(scope="module")
def f_market() -> Market:
    return market_of(factor_history(), F_DAYS[0])


def test_factor_facts_for_f4(f_market):
    out = evidence.evidence_for("FACTOR", f_market, F4, F_DATE, ["EEE", "DDD", "AAA", "SPY"])
    assert set(out) == {"EEE", "DDD", "AAA"}  # SPY is never a factor stock
    assert_plain(out)
    assert_distinct(out)
    assert out["EEE"][0].startswith("Its price rose ") and out["EEE"][0].endswith("from 12 months ago to 1 month ago.")
    assert out["EEE"][1] == "It ranked 1st of 5 stocks checked on that move, strongest first."
    assert out["AAA"][1] == "It ranked 5th of 5 stocks checked on that move, strongest first."
    assert out["EEE"][2].startswith("SPY closed ") and "above its 200-day average" in out["EEE"][2]
    assert out["EEE"][2].endswith("so the method is allowed to hold stocks.")
    assert len(out["EEE"]) == 3  # momentum ranking: no volatility fact


def test_factor_volatility_is_stated_only_when_the_ranking_reads_it(f_market):
    calm = FactorParams("lowvol", top=2, trend=None, min_dollar_volume=0.0)
    out = evidence.evidence_for("FACTOR", f_market, calm, F_DATE, ["AAA", "EEE"])
    assert_plain(out)
    for facts in out.values():
        assert "calmest first" in facts[1]
        assert "a day over the last 60 trading days" in facts[2]
        assert len(facts) == 3  # no trend: no market-filter fact


def test_factor_reads_nothing_after_the_data_date():
    h = factor_history()
    symbols = sorted(h)
    base = evidence.evidence_for("FACTOR", market_of(cut_at(h, F_DATE), F_DAYS[0]), F4, F_DATE, symbols)
    wild = evidence.evidence_for("FACTOR", market_of(later_bars_changed(h, F_DATE), F_DAYS[0]), F4, F_DATE, symbols)
    assert base == wild and base


# --------------------------------------------------------------------------- TIMING (F1)


def test_timing_facts_for_f1(f_market):
    out = evidence.evidence_for("TIMING", f_market, F1, F_DATE, ["SPY", "BIL"])
    assert set(out) == {"SPY"}
    assert_plain(out)
    first, rule = out["SPY"]
    assert first.startswith("SPY closed at $") and "above its 200-day average of $" in first
    assert rule == "The rule holds SPY while SPY closes above its 200-day average, so it holds SPY."


def test_timing_explains_nothing_when_the_rule_is_off():
    falling = {"SPY": hist("SPY", [500.0 - 0.5 * t for t in range(len(F_DAYS))], days=F_DAYS)}
    assert evidence.evidence_for("TIMING", market_of(falling, F_DAYS[0]), F1, F_DATE, ["SPY"]) == {}


@pytest.mark.parametrize(
    "params, needle",
    [
        (TimingParams(hold="SSO", signal="SPY", rule="month_sma", n=10), "month-end closes"),
        (TimingParams(hold="SSO", signal="SPY", rule="abs_mom", n=252), "12 months earlier"),
        (TimingParams(hold="SSO", signal="SPY", rule="always", n=1), "at all times"),
    ],
)
def test_timing_other_rules(f_market, params, needle):
    h = dict(factor_history())
    h["SSO"] = hist("SSO", uptrend(len(F_DAYS), first=60.0), days=F_DAYS)
    out = evidence.evidence_for("TIMING", market_of(h, F_DAYS[0]), params, F_DATE, ["SSO"])
    assert_plain(out)
    assert any(needle in fact for fact in out["SSO"])


def test_timing_reads_nothing_after_the_data_date():
    h = factor_history()
    base = evidence.evidence_for("TIMING", market_of(cut_at(h, F_DATE), F_DAYS[0]), F1, F_DATE, ["SPY"])
    wild = evidence.evidence_for("TIMING", market_of(later_bars_changed(h, F_DATE), F_DAYS[0]), F1, F_DATE, ["SPY"])
    assert base == wild and base


# --------------------------------------------------------------------------- FUNDAMENTAL (FND)

FND_SYMBOLS = ("AAA", "BBB", "CCC", "DDD", "EEE")
FND_DAYS = session_days(230, date(2026, 1, 2))
FND_DATE = date(2026, 10, 30)


def fnd_history() -> dict[str, History]:
    return {
        s: hist(s, [6.0 + 2.0 * k + 0.002 * i for i in range(len(FND_DAYS))], days=FND_DAYS, volume=5_000_000.0)
        for k, s in enumerate(FND_SYMBOLS)
    }


def _fact(symbol: str, tag: str, unit: str, start: date | None, end: date, val: float, filed: date,
          taxonomy: str = "us-gaap", form: str = "10-K") -> Fact:
    return Fact(symbol=symbol, taxonomy=taxonomy, tag=tag, unit=unit, period_start=start, period_end=end,
                val=float(val), accn=f"{symbol}-{tag}-{end:%Y%m%d}", form=form, fy=end.year,
                fp="FY" if form == "10-K" else "Q", filed=filed)


_QUARTERS = [
    (date(y, m0, 1), date(y, m1, d1))
    for y in (2024, 2025, 2026)
    for m0, m1, d1 in ((1, 3, 31), (4, 6, 30), (7, 9, 30), (10, 12, 31))
][:10]
_EPS = (1.00, 1.10, 1.20, 1.30, 1.45, 1.70, 1.55, 1.80, 2.10, 2.00)


def fnd_panel(extra: tuple[Fact, ...] = ()) -> FundamentalPanel:
    """A real panel with every factor finite (the quarterly EPS run gives SUE), as test_paper_fnd builds it."""
    year_start, year_end, filed = date(2025, 1, 1), date(2025, 12, 31), date(2026, 2, 20)
    facts: list[Fact] = []
    for k, s in enumerate(FND_SYMBOLS):
        facts.append(_fact(s, "Assets", "USD", None, year_end, 1_000_000_000.0 + 1e8 * k, filed))
        facts.append(_fact(s, "StockholdersEquity", "USD", None, year_end, 400_000_000.0 + 2e7 * k, filed))
        facts.append(_fact(s, "EntityCommonStockSharesOutstanding", "shares", None, year_end,
                           10_000_000.0 + 1e6 * k, filed, taxonomy="dei"))
        facts.append(_fact(s, "NetIncomeLoss", "USD", year_start, year_end, 50_000_000.0 + 5e6 * k, filed))
        facts.append(_fact(s, "GrossProfit", "USD", year_start, year_end, 400_000_000.0 + 3e7 * k, filed))
        for i, (q_start, q_end) in enumerate(_QUARTERS):
            facts.append(_fact(s, "EarningsPerShareDiluted", "USD/shares", q_start, q_end, _EPS[i] + 0.07 * k,
                               q_end + timedelta(days=40), form="10-Q"))
    return FundamentalPanel.from_facts(tuple(facts) + extra)


@pytest.fixture(scope="module")
def fnd_market() -> Market:
    return market_of(fnd_history(), FND_DAYS[0], fnd_panel())


def test_fundamental_facts_for_fnd(fnd_market):
    out = evidence.evidence_for("FUNDAMENTAL", fnd_market, FND, FND_DATE, list(FND_SYMBOLS))
    assert set(out) == set(FND_SYMBOLS)
    assert_plain(out)
    assert_distinct(out)
    places = sorted(facts[0].split()[2] for facts in out.values())
    assert places == ["1st", "2nd", "3rd", "4th", "5th"]
    for facts in out.values():
        assert len(facts) == 6
        assert "of 5 companies checked on a combined score of 4 measures" in facts[0]
        assert "of its stock-market value" in facts[1]
        assert "on its shareholders' money" in facts[2]
        assert "of everything it owns" in facts[3]
        assert "the same quarter a year earlier" in facts[4]
        assert facts[5] == "Its latest financial filing used here is 252 days old."  # 2026-02-20 -> 2026-10-30
        assert re.search(r"(the highest of the 5|the lowest of the 5|higher than \d+% of the other) companies checked\.$", facts[1])


def test_fundamental_single_factor(fnd_market):
    out = evidence.evidence_for("FUNDAMENTAL", fnd_market, FundamentalParams(rank="quality", top=2), FND_DATE, ["AAA", "EEE"])
    assert_plain(out)
    for facts in out.values():
        assert "how much it earns on its shareholders' money, highest first" in facts[0]
        assert len(facts) == 3


def test_fundamental_without_a_panel_explains_nothing():
    assert evidence.evidence_for("FUNDAMENTAL", market_of(fnd_history(), FND_DAYS[0]), FND, FND_DATE, ["AAA"]) == {}


def test_fundamental_reads_nothing_after_the_data_date():
    h = fnd_history()
    later = date(2026, 11, 3)
    assert later > FND_DATE
    restated = tuple(
        _fact(s, "StockholdersEquity", "USD", None, date(2026, 9, 30), 9e9, later) for s in FND_SYMBOLS
    )
    base = evidence.evidence_for("FUNDAMENTAL", market_of(cut_at(h, FND_DATE), FND_DAYS[0], fnd_panel()), FND, FND_DATE, list(FND_SYMBOLS))
    wild = evidence.evidence_for(
        "FUNDAMENTAL", market_of(later_bars_changed(h, FND_DATE), FND_DAYS[0], fnd_panel(restated)), FND, FND_DATE, list(FND_SYMBOLS)
    )
    assert base == wild and base


# --------------------------------------------------------------------------- formatting


@pytest.mark.parametrize(
    "fn, x, expected",
    [
        (evidence._pct, 0.0614, "6.1%"),
        (evidence._pct, -0.31, "31%"),
        (evidence._money, 1231.4, "$1,231.40"),
        (evidence._big_money, 45_200_000.0, "$45 million"),
        (evidence._big_money, 1_230_000_000.0, "$1.2 billion"),
        (evidence._ordinal, 1, "1st"),
        (evidence._ordinal, 12, "12th"),
        (evidence._ordinal, 22, "22nd"),
        (evidence._ordinal, 413, "413th"),
        (evidence._span, 252, "12 months"),
        (evidence._span, 21, "1 month"),
        (evidence._span, 5, "5 trading days"),
    ],
)
def test_formatting(fn, x, expected):
    assert fn(x) == expected


def test_every_function_is_deterministic(a_market, f_market, fnd_market):
    for name, m, p, d, symbols in (
        ("STRATEGY_A", a_market, STRATEGY_A_PARAMS, A_DATE, ["AAA", "BBB"]),
        ("FACTOR", f_market, F4, F_DATE, ["AAA", "EEE"]),
        ("TIMING", f_market, F1, F_DATE, ["SPY"]),
        ("FUNDAMENTAL", fnd_market, FND, FND_DATE, ["AAA", "EEE"]),
    ):
        assert evidence.evidence_for(name, m, p, d, symbols) == evidence.evidence_for(name, m, p, d, symbols)


def test_facts_are_plain_str(a_market, fnd_market):
    """Facts are exact ``str`` values (JSON-ready for phase 2's jsonb column), never numpy strings."""
    for out in (
        evidence.evidence_for("STRATEGY_A", a_market, STRATEGY_A_PARAMS, A_DATE, ["AAA"]),
        evidence.evidence_for("FUNDAMENTAL", fnd_market, FND, FND_DATE, ["AAA"]),
    ):
        assert out and all(type(f) is str for facts in out.values() for f in facts)
