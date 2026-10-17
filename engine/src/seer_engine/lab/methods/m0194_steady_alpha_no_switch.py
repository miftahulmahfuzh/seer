"""M0194 — Steady beaters with no switch: the three-year alpha leaders among betas near one, fully
invested through every crash.

Source: variation of M0188, Sera batch 20261017-1808. The clean test M0188 meant to run: M0188's
hypothesis said "no market switch", but its screen (``FactorParams``) defaults ``trend`` to the
SPY 200-day switch and the method file never overrode it, so all five of its books sat in cash
through 2001-2002 and 2008-2009. Its recorded trials describe what ran; they cannot say whether
alpha picks hold up in a crash. This method asks that, with ``trend=None`` set explicitly on every
variant (Sera note 2 of the batch).

Everything else is M0188's, and the allocator is M0188's own object, imported rather than copied,
so the measure (156 non-overlapping weekly log returns, CAPM beta and alpha to SPY on raw
returns), the 0.8-1.2 beta band, the quarterly re-pick with a 40% keep band, equal slots, unfilled
slots in SPY and the fees are byte-for-byte the ones M0188 ran. The configuration digests still
differ from M0188's because ``inner.trend`` is part of the params. The t-statistic reading is
dropped: it trailed plain alpha on every measure in M0188.

Yardstick (Sera note 1): the placebo book M0187 fills this same equal-weight quarterly frame in a
meaningless order. Its no-switch seeds earned +8.8% to +11.9% a year on the deposits with worst
falls of 52-61%, so a no-switch alpha book is judged against that spread, not only against SPY.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees, asked monthly.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0188_steady_alpha_beta_band import STEADY_ALPHA, SteadyAlphaParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.f_factor import FactorParams

ADDED = date(2026, 10, 17)


def _screen(top: int) -> FactorParams:
    # The rank is unused (only the screen). trend=None is the point of this method: no switch.
    return FactorParams(rank="momentum", top=top, trend=None)


def _v(suffix: str, params: SteadyAlphaParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0194-{suffix}", family="M0194", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=STEADY_ALPHA, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0194",
    name=(
        "Steady beaters with no switch: the three-year alpha leaders among betas near one, fully "
        "invested through every crash"
    ),
    family="stock-alpha-persistence",
    source_kind="variation",
    source_ref=(
        "variation of M0188 (the same alpha ranking, run as its hypothesis asked: no SPY 200-day "
        "switch); Jensen (1968) alpha; De Bondt & Thaler (1985) long-term reversal as the "
        "counter-claim; Sera batch 20261017-1808"
    ),
    parent_id="M0188",
    hypothesis=(
        "The clean test M0188 meant to run. M0188's books accidentally ran behind the SPY 200-day "
        "switch (the screen's default trend), so they sat in cash through 2001-2002 and 2008 and "
        "could not show whether alpha picks hold up in a crash. Same measures and frame as M0188 "
        "(156 weekly returns, CAPM alpha, beta 0.8 to 1.2, quarterly with a 40% keep band, equal "
        "weight, unfilled slots in SPY, fractional at Gotrade's real fees on the owner's "
        "deposits, M0188's own allocator) with the trend set to None explicitly on every variant. "
        "Variants: A20, A40, and the low-alpha control L20 (the t-statistic reading is dropped: it "
        "trailed plain alpha everywhere in M0188). Yardstick: the placebo book (M0187), the same "
        "frame filled in a meaningless order, earned +8.8% to +11.9% a year on the deposits "
        "without a switch with worst falls of 52-61%; an alpha book whose result sits inside that "
        "spread is the frame, not the ranking. Each variant's beta to SPY is reported. Success: "
        "A20 beats SPY TR on the deposits and the top of the placebo spread, its 2008 fall is "
        "clearly shallower than L20's, the placebo's and the beta-band coskewness book's (44%), "
        "the month-by-month gap over L20 reaches a t-statistic near 2, and a majority of "
        "walk-forward folds are won. Not a strongly published anomaly (stock-level alpha "
        "persistence is folklore; Jensen 1968 measured funds). Designed from the dev window only."
    ),
    expected_failure=(
        "Without the switch the 2008 fall sits near 45-55% and fails the 25% bar (the dev screen "
        "for a no-switch book is looser, but the go-live bar is not); the 2-point gap over the "
        "low-alpha control shrinks or vanishes once crash months count, because three-year "
        "winners are not safer in a crash than three-year losers when beta is held near one; the "
        "result lands inside the placebo's +8.8% to +11.9% spread; the equal-weight lean keeps "
        "2009-2015 behind SPY; the walk-forward splits. If the gap does hold, the next step is a "
        "30% sleeve beside a SPY core, not a standalone book."
    ),
    candidates=(
        _v("A20", SteadyAlphaParams(_screen(20)),
           "The 20 members with the highest three-year alpha among betas 0.8 to 1.2, no switch"),
        _v("A40", SteadyAlphaParams(_screen(40)),
           "A 40-name rung of the same book, no switch"),
        _v("L20", SteadyAlphaParams(_screen(20), low=True),
           "Control for A20: the 20 lowest three-year alphas in the same beta band, no switch"),
    ),
    seen_keys=(
        "concept:beta-banded-capm-alpha-no-switch",
        "concept:stock-alpha-persistence",
    ),
)
