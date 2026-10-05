"""M0005 - Point-in-time fundamental factors: value, quality, gross profitability and SUE.

Source: Fama & French (1992), "The cross-section of expected stock returns", Journal of Finance
47(2) (book-to-market); Novy-Marx (2013), "The other side of value: the gross profitability
premium", Journal of Financial Economics 108(1); Bernard & Thomas (1989), "Post-earnings-
announcement drift", Journal of Accounting Research 27 (SUE on a seasonal random walk).

Idea: the lab has only ever ranked on price history. SEC EDGAR gives the four factor families
best documented after momentum, point in time, for free, including for the 133 ever-members
that no longer trade. Each fact's ``filed`` date is the availability boundary, so nothing here
can see a figure before the market could.

The allocator is ``strategies.f_fundamental.FUNDAMENTAL`` (id "FND"). Its live path is
``prepare_market``: fundamentals cannot travel through ``prepare(history)``, and the lab's
config digest forbids carrying bulk data in ``params``. With no panel the allocator targets
nothing, which is the honest reading of "no filing is known".

READ THIS BEFORE RUNNING: ``lab run`` loads the research store. Phase 6 taught the store to
carry a ``fundamentals.csv`` panel, but it is an OPTIONAL file: a store on disk that was built
before that phase, or rebuilt without ``--with-fundamentals``, loads cleanly with an EMPTY
panel and no warning. Running M0005 against such a store records six all-cash trials, freezes
this file's ``source_sha`` and burns the method id for good - ``runner.preflight`` refuses a
second run of any method. So the gate is not "has phase 6 landed" but "has THIS store been
rebuilt with a panel". Check it first::

    python -c "import json,pathlib; print('fundamentals.csv' in json.loads(pathlib.Path('engine/.research/manifest.json').read_text())['files'])"

Do not run ``lab run M0005`` until that prints True. See the phase 7 plan's Handoffs.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalParams

ADDED = date(2026, 10, 5)

# Every variant: top 20, no trend gate, the shipped liquidity floors. lookback is DV_N = 20.
VALUE = FundamentalParams(rank="value", top=20)
QUALITY = FundamentalParams(rank="quality", top=20)
PROFITABILITY = FundamentalParams(rank="profitability", top=20)
SUE = FundamentalParams(rank="sue", top=20)
COMPOSITE = FundamentalParams(rank="composite", top=20)
COMPOSITE_RANK = FundamentalParams(rank="composite", top=20, sizing="rank")


def _v(suffix: str, params: FundamentalParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0005-{suffix}", family="M0005", rules=MONTHLY_HOLD, allocator=FUNDAMENTAL,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0005",
    name="Point-in-time fundamental factors from SEC EDGAR",
    family="stock-fundamental-cross-section",
    source_kind="paper",
    source_ref=(
        "Fama & French (1992), The cross-section of expected stock returns, JF 47(2); "
        "Novy-Marx (2013), The other side of value, JFE 108(1); "
        "Bernard & Thomas (1989), Post-earnings-announcement drift, JAR 27"
    ),
    hypothesis=(
        "Every lab method so far ranks on price alone. The four fundamental factor families with "
        "the longest out-of-sample record - book-to-price, return on equity, gross profitability "
        "and standardized unexpected earnings - are now available point in time from EDGAR, with "
        "each fact gated on its filed date. Ranking the top 20 index members on the equal-weighted "
        "z-score composite of the four, monthly, beats SPY total return over the dev window at a "
        "max drawdown below a price-momentum book's, because the four are weakly correlated with "
        "each other and with momentum."
    ),
    expected_failure=(
        "Large-cap index members are the segment where these premia are weakest: the universe is "
        "already screened for size and liquidity, so the cross-sectional spread in book-to-price "
        "and gross profitability is too narrow to pay for monthly turnover, and every variant "
        "lands within noise of SPY. Or the staleness gate bites: annual filers go more than 400 "
        "days between usable facts, the eligible set collapses below 20 names in parts of the "
        "window, and the book runs half in cash for reasons that have nothing to do with the signal."
    ),
    candidates=(
        _v("VAL", VALUE,
           "Book-to-price alone: equity over filed-dated shares times close, the Fama-French value leg"),
        _v("ROE", QUALITY,
           "Return on equity alone: annual net income over book equity, the quality leg"),
        _v("GP", PROFITABILITY,
           "Gross profitability alone: annual gross profit over assets, Novy-Marx's other side of value"),
        _v("SUE", SUE,
           "SUE alone: the seasonal random walk surprise, post-earnings-announcement drift"),
        _v("ALL", COMPOSITE,
           "Equal-weighted z-score composite of all four, equal position weights"),
        _v("ALL-R", COMPOSITE_RANK,
           "The same composite with linear rank weights: does conviction in the top names pay"),
    ),
    seen_keys=(
        "concept:point-in-time-fundamental-factor-composite",
        "url:https://doi.org/10.1016/j.jfineco.2013.01.003",
    ),
)
