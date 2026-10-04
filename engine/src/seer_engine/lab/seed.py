"""The lab's starting record: everything tried before the lab existed (method lab design §1).

- P7a's 54 dev-window candidates become trials 1–54 (registry order), grouped into one closed
  method per P7a family (``H-P7A-F1`` …). Metrics and month-end curves come from the committed
  P7a report files; nothing is re-run. DSR is NULL (P7a reported it for one row only).
- Strategies A, A2 and B become closed methods without trials: they ran on windows after the
  dev window (P3's out-of-sample, P3b/P6a walk-forwards), not on the lab's dev window.

So the lab's N starts at 54, not at 0.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from seer_engine import config
from seer_engine.backtest.registry import REGISTRY
from seer_engine.lab import store
from seer_engine.lab.method import config_digest, config_text

BACKTESTS = config.REPO_ROOT / "docs" / "backtests"
P7A_ROWS = BACKTESTS / "2026-10-04-p7a-dev-exploration-rows.csv"
P7A_CURVES = BACKTESTS / "2026-10-04-p7a-dev-exploration-curves.csv"
P7A_GIT_SHA = "b2ec090"  # the commit that registered entries 1-54
P7A_FINGERPRINT = "5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a"
P7A_RUN_AT = "2026-10-04T00:00:00+00:00"
P7A_REPORT = "docs/backtests/2026-10-04-p7a-dev-exploration.md"
# The P7a research store behind fingerprint P7A_FINGERPRINT (P7A_REPORT, "Data"): shown on
# seertrade.site/sera through store.snapshot. The store itself is local and gitignored.
P7A_BAR_ROWS = 2_490_793
P7A_SYMBOLS_REQUESTED = 1_061
P7A_SYMBOLS_SERVED = 539
P7A_DIVIDEND_ROWS = 28_206

P7A_FAMILIES: dict[str, tuple[str, str]] = {
    "REF": ("P7a references (SPY hold, A on design-v0)", "Sanity references: SPY held with dividends; A's idea on fresh data"),
    "F1": ("Index trend timing (SMA / 10-month / abs-momentum on SPY, QQQ)", "A trend filter on the index cuts crash drawdowns while keeping most of the upside"),
    "F2": ("Dual momentum (SPY/QQQ/EFA, bonds fallback)", "Relative plus absolute momentum between a few index ETFs beats holding one"),
    "F3": ("Sector ETF rotation", "Sector leadership persists for months; holding the top sectors beats the index"),
    "F4": ("Cross-sectional stock momentum (12-1, 6-1) with a SPY trend filter", "Past winners keep winning; the trend filter avoids momentum crashes"),
    "F5": ("Low-volatility stocks", "The low-volatility anomaly: calm stocks earn index-like returns with smaller drawdowns"),
    "F6": ("Momentum among low-volatility stocks", "Combining momentum with low volatility keeps the return and cuts the drawdown"),
    "F7": ("RSI(2) mean-reversion swing trades", "Short-term oversold dips in uptrending stocks bounce within days"),
    "F9": ("Blends: timed SPY core plus a momentum or swing satellite", "Diversifying across uncorrelated sleeves lowers drawdown"),
    "F10": ("Leveraged index ETFs above trend", "2x exposure only in uptrends compounds faster than the index (needs owner: leverage)"),
    "F11": ("Turn-of-month calendar effect", "Most of the index return arrives around the turn of the month; low exposure, low drawdown"),
}

HISTORICAL: tuple[tuple[str, str, str, str, str], ...] = (
    ("H-A", "Strategy A (design-v0 bracket swing picks)", "bracket-swing",
     "Ranked oversold large caps bought on a limit with TP/SL and a 5-day time stop beat SPY",
     "P3 gate failed: out of sample 2022-01-03 -> 2026-10-02 it returned -15.0% vs +71.9% for SPY TR, PF 0.92, max DD 33.3% (docs/backtests/2026-10-02-strategy-a.md)."),
    ("H-A2", "Strategy A2 (A + regime/calm/floor variants, walk-forward)", "bracket-swing",
     "A with a SPY regime filter and calmer candidates survives the walk-forward",
     "P3b gate failed: walk-forward 2018-01-02 -> 2026-10-02 returned +9.1% vs +187.6% SPY TR, PF 1.02, max DD 29.1%; 324 combinations per fold (docs/backtests/2026-10-02-strategy-a2-walkforward.md)."),
    ("H-B", "Strategy B (gradient-boosted ranker on A's bracket)", "ml-ranker",
     "A tree model on cross-sectional feature ranks picks brackets with positive net return",
     "P6a gate failed: walk-forward 2018-01-02 -> 2026-10-02 returned +13.3% vs +187.6% SPY TR, PF 1.03, max DD 57.6% (docs/backtests/2026-10-02-strategy-b-walkforward.md)."),
)


def _num(s: str) -> float | None:
    return None if s == "" else float(s)


def _curves() -> dict[str, list[list[object]]]:
    with P7A_CURVES.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        out: dict[str, list[list[object]]] = {}
        for rec in reader:
            for key, value in rec.items():
                if key in ("date", "spy_price", "spy_tr") or value == "":
                    continue
                out.setdefault(key, []).append([rec["date"], float(value)])
    return out


def benchmark_curves() -> dict[str, list[tuple[str, float]]]:
    """SPY's month-end growth of 1 over the dev window, from the committed P7a curves file:
    ``spy_tr`` (dividends reinvested) and ``spy_price`` (price only), 1993-01-29 = 1.0 through
    2015-10-16, rounded to 6 dp. Trials store only SPY's totals; the web draws this line."""
    out: dict[str, list[tuple[str, float]]] = {"spy_tr": [], "spy_price": []}
    with P7A_CURVES.open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            for key, points in out.items():
                if rec[key] != "":
                    points.append((rec["date"], round(float(rec[key]), 6)))
    return out


def seed(conn: sqlite3.Connection) -> int:
    """Import the historical record into an empty lab. Returns the number of trials added."""
    if conn.execute("SELECT count(*) FROM methods").fetchone()[0]:
        raise store.LabError("the lab is not empty; the seed import runs once")
    by_id = {c.id: c for c in REGISTRY}
    with P7A_ROWS.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if [r["id"] for r in rows] != [c.id for c in REGISTRY[: len(rows)]]:
        raise store.LabError("the P7a rows file is not in registry order")
    curves = _curves()
    trials: list[store.TrialRow] = []
    for r in rows:
        c = by_id[r["id"]]
        failed = [x for x in r["failed"].split(";") if x]  # DSR unknown, so not listed
        trials.append(store.TrialRow(
            method_id=f"H-P7A-{r['family']}",
            candidate_id=c.id,
            config_digest=config_digest(c),
            config_text=config_text(c),
            rules_id=c.rules.id,
            allocator_id=str(c.allocator.id),
            window="dev",
            start=r["start"],
            end=r["end"],
            store_fingerprint=P7A_FINGERPRINT,
            git_sha=P7A_GIT_SHA,
            run_at=P7A_RUN_AT,
            total_return=_num(r["total_return"]),
            cagr=_num(r["cagr"]),
            max_drawdown=_num(r["max_drawdown"]),
            profit_factor=_num(r["profit_factor"]),
            trades=int(r["trades"]),
            sharpe=_num(r["sharpe"]),
            exposure=_num(r["exposure"]),
            turnover=_num(r["turnover"]),
            worst_year=None if r["worst_year"] == "" else int(r["worst_year"]),
            worst_year_return=_num(r["worst_year_return"]),
            spy_tr_return=_num(r["spy_tr_total_return"]),
            spy_tr_cagr=_num(r["spy_tr_cagr"]),
            mar=_num(r["mar"]),
            failed="; ".join(failed),
            eligible=False,
            dsr=None,
            n_trials_at_run=len(rows),
            curve_json=json.dumps(curves.get(c.id, []), separators=(",", ":")),
        ))
    with conn:
        for fam, (name, hypothesis) in P7A_FAMILIES.items():
            store.add_method(
                conn, id=f"H-P7A-{fam}", name=name, family=f"p7a-{fam.lower()}", source_kind="seed",
                source_ref=P7A_REPORT, hypothesis=hypothesis, status="rejected",
                verdict="P7a: none eligible on the dev window; every candidate failed max DD <= 15%",
                allow_any_status=True,
            )
        for mid, name, family, hypothesis, verdict in HISTORICAL:
            store.add_method(
                conn, id=mid, name=name, family=family, source_kind="seed", source_ref="docs/ROADMAP.md",
                hypothesis=hypothesis, status="rejected", verdict=verdict, allow_any_status=True,
            )
        store.insert_trials(conn, trials)
        for c in REGISTRY:
            store.mark_seen(conn, f"concept:{c.id.lower()}", f"H-P7A-{c.family}", c.rationale)
    return len(trials)
