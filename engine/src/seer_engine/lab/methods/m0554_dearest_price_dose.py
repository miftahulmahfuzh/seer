"""M0554 -- Does the dearest-price lead grow as the book gets more extreme? 10, 20 and 40 names.

Parent: M0536 (closest: M0531, M0383). Reserved by Sera batch 20261113-0539 as an ``idea`` row;
this file refines it and keeps its id.

M0383-HIGH20 (the 20 highest printed share prices behind SPY's 200-day switch) ranked 2nd of 11
against ten matched blind draws (M0531's four, M0536's six). A place luck reaches about 2 times in
11 is not a lead, and it trailed SPY in 2009-2015. A real price effect is a *dose* effect: pick
only the 10 dearest and the lead over matched draws should widen, pick 40 and it should thin. Luck
has no reason to line up that way. So this method builds the ladder.

Arms (all fractional shares at Gotrade's real fees, ``MONTHLY_HOLD_FRAC_GOTRADE``, as M0383 and
M0531 ran; the pool, rank and switch are imported from M0531, not copied):

* ``HIGH10`` and ``HIGH40`` -- the treatments, M0531's dearest-price rule at 10 and 40 names.
* ``BLIND10-A/B`` and ``BLIND40-A/B`` -- two matched blind draws per size (seeds 554-557), each
  matched on its own treatment's book size, entry count and churn. Two draws give a thin spread
  per rung, which is why the readout also uses the ten recorded size-20 draws as the spread
  yardstick. HIGH20 and its ten draws are recorded (M0383-HIGH20 / M0531 / M0536) and are not
  re-run; re-running would be a book twin.

Readout, fixed now: compute each rung's lead = treatment funded CAGR minus the mean of its own
matched draws, for 10, 20 (recorded: HIGH20 vs the ten) and 40. Keep the family only if the
leads rise monotonically HIGH40 < HIGH20 < HIGH10 and HIGH10's lead exceeds the size-20 draws'
standard deviation. Otherwise retire it.

Published-anomaly note: Birru & Wang (2016) is recent and the dev window ends in 2015, so a dev
edge is from before the crowd and may fade.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0531_dearest_price_disproof import BLIND, DEAR, SW, DearParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 13)


def _v(suffix: str, allocator, params: DearParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0554-{suffix}", family="M0554", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _high(n: int) -> Candidate:
    return _v(f"HIGH{n}", DEAR, DearParams(top=n, side="high", trend=SW),
              f"The treatment: the {n} highest printed prices in the screened pool, behind the "
              "switch.")


def _blind(n: int, letter: str, seed: int) -> Candidate:
    return _v(f"BLIND{n}-{letter}", BLIND, DearParams(top=n, side="random", seed=seed, trend=SW),
              f"Control: blind draw {letter} (seed {seed}) matched on HIGH{n}'s own size, entry "
              "count and churn, same pool and switch, none of its names.")


METHOD = Method(
    id="M0554",
    name="Dearest printed price at 10, 20 and 40 names, each against random books of its own size",
    family="stock-nominal-price-level",
    source_kind="variation",
    source_ref=('Birru & Wang (2016), "Nominal Price Illusion", JFQA; parent M0536, '
                "closest M0531, M0383"),
    parent_id="M0536",
    hypothesis=(
        "M0383-HIGH20 (the 20 highest printed share prices behind SPY's 200-day switch) ranked "
        "2nd of 11 against ten matched blind draws from M0531 and M0536, a place luck reaches "
        "about 2 times in 11, and trailed SPY in 2009-2015 (recorded figures, re-read before "
        "quoting). If the price rank is real, the lead over matched draws should grow as the book "
        "gets more extreme: HIGH10 above HIGH20 above HIGH40. Arms: HIGH10 and HIGH40, each with "
        "two matched blind draws of its own size (seeds 554-557); HIGH20 and its ten draws are "
        "recorded and not re-run. Readout fixed now: lead = treatment funded CAGR minus the mean "
        "of its own draws; keep the family only if leads rise HIGH40 < HIGH20 < HIGH10 and "
        "HIGH10's lead exceeds the standard deviation of the ten size-20 draws; otherwise retire "
        "it. All books fractional at Gotrade's real fees. Prediction: no monotone ladder; HIGH10 "
        "is just a more concentrated, noisier book and the family retires. Published 2016, so a "
        "dev edge is from before the crowd and may fade."
    ),
    expected_failure=(
        "The leads do not line up: HIGH10 inside its two draws' spread, or HIGH40 leading as much "
        "as HIGH20. Two draws per rung is a thin spread, so a mixed ladder is read against the "
        "ten size-20 draws, not declared a result. HIGH10 holds 10 slots, so fees and a single "
        "name's gap weigh more. 2009-2015 may again lag SPY."
    ),
    candidates=(
        _high(10), _blind(10, "A", 554), _blind(10, "B", 555),
        _high(40), _blind(40, "A", 556), _blind(40, "B", 557),
    ),
    seen_keys=(
        "concept:dearest-price-dose-ladder",
        "concept:nominal-price-level-draw-spread",
    ),
)
