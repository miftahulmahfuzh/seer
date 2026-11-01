"""M0428 — Volatility-managed SPY with a higher target: nearly fully invested, out only in storms.

Source: variation of M0423 (Moreira & Muir 2017, Volatility-Managed Portfolios).
M0423's 15% target held 85% of SPY on average and gave up about 0.7 points a year to
always-100% for a shallower fall. This raises the target to 20% and 25% so the book is stepped
back only when variance is extreme, and runs always-invested controls at the same average
exposure. The sizing rule is M0423's, imported, not re-implemented. Pure.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0423_volatility_managed_spy import Params, VolManagedAlloc
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 1)


class HighTargetAlloc(VolManagedAlloc):
    """M0423's SPY-only exposure rule under this method's own allocator id."""

    id = "M0428"


ALLOC = HighTargetAlloc()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0428-{suffix}", family="M0428",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ALLOC, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0428",
    name="Volatility-managed SPY with a higher target: stay nearly fully invested and step back only in storms",
    family="volatility-managed-exposure",
    source_kind="variation",
    source_ref="M0423",
    parent_id="M0423",
    hypothesis=(
        "M0423 found variance-scaled SPY cut the worst fall from 55% to about 35% but earned "
        "about what a flat 80% book did, 0.7 points a year behind always-100%. Raise the "
        "annualized volatility target to 20% and 25% (no leverage, 21-day window, 5% steps, "
        "monthly, fractional shares at Gotrade fees) so the book holds nearly all of SPY in calm "
        "years and steps back only in storms. Published 2017; the dev window ends before the "
        "crowd traded it. Arms: VAR21-T20 and VAR21-T25 (variance rule at the two targets), "
        "VOL21-T25 (volatility rule, the gentlest), and three always-invested controls with no "
        "opinion at the average exposure each managed arm would have held: FLAT90 (VAR21-T20, "
        "0.899), FLAT95 (VAR21-T25, 0.945) and FLAT100 (the zero of the dial). Averages are of "
        "the monthly weight on SPY closes 1996-2015, read before the run, no return. The signal "
        "is real only if each managed arm beats its flat twin on worst fall without losing "
        "return; the SPY comparison is FLAT100 against the flats. 2009-2015 had no bear market, "
        "so expect lag there; the question is whether the 25% fall bar holds at 95% exposure."
    ),
    expected_failure=(
        "It fails 'beats SPY' as M0423 did: any exposure under 100% is cash time in a rising "
        "market, and the storms it avoids (2000-02, 2008) are too few to repay the calm-year "
        "drag plus a Gotrade minimum fee on each monthly 5% re-size. At 95% exposure the worst "
        "fall probably stays near SPY's 55%, failing the drawdown bar, so the higher target buys "
        "back return by giving up the very protection that justified the rule. The managed arms "
        "probably match their flat twins within noise."
    ),
    candidates=(
        _v("VAR21-T20", Params(mode="var", n=21, target_pct=20), "variance rule, 20% target"),
        _v("VAR21-T25", Params(mode="var", n=21, target_pct=25), "variance rule, 25% target"),
        _v("VOL21-T25", Params(mode="vol", n=21, target_pct=25), "volatility rule, 25% target"),
        _v("FLAT90", Params(mode="flat", flat=90), "control: always 90% invested"),
        _v("FLAT95", Params(mode="flat", flat=95), "control: always 95% invested"),
        _v("FLAT100", Params(mode="flat", flat=100), "control: always fully invested"),
    ),
    seen_keys=("concept:volatility-managed-spy-high-target",),
)
