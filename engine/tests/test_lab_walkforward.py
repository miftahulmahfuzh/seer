"""Walk-forward: choose on the train slice, score on the slice it has never seen."""

from __future__ import annotations

from datetime import date

import pytest

from seer_engine.lab import walkforward as wf


def months(first: date, n: int) -> list[date]:
    """``n`` month-end-ish dates, one a month, ascending."""
    out, y, m = [], first.year, first.month
    for _ in range(n):
        out.append(date(y, m, 28))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def curve(ms: list[date], monthly: float, start: float = 1.0) -> list[tuple[date, float]]:
    """A curve compounding at a flat ``monthly`` rate."""
    out, v = [], start
    for d in ms:
        out.append((d, v))
        v *= 1.0 + monthly
    return out


M240 = months(date(1996, 1, 1), 240)  # twenty years, like the dev window


# --------------------------------------------------------------------------- folds

def test_folds_expand_the_train_slice_and_step_the_evaluation_slice():
    got = wf.folds(M240, min_train_years=10, eval_years=3)
    assert [f.index for f in got] == [1, 2, 3, 4]
    assert got[0].train_end == date(2006, 1, 1)
    assert got[0].eval_start.year == 2006 and got[0].eval_end.year == 2008
    assert got[1].train_end == date(2009, 1, 1)
    assert got[2].train_end == date(2012, 1, 1)
    assert got[3].train_end == date(2015, 1, 1)
    # train slices expand, never slide
    assert got[0].train_end < got[1].train_end < got[2].train_end


def test_a_tail_too_thin_to_read_is_dropped_rather_than_reported():
    """Fourteen months left over is a fold; two months is not."""
    assert all(
        f.eval_end >= f.eval_start for f in wf.folds(months(date(1996, 1, 1), 194))
    )
    thin = wf.folds(months(date(1996, 1, 1), 182), min_train_years=10, eval_years=3)
    assert all(
        len([d for d in months(date(1996, 1, 1), 182) if f.eval_start <= d <= f.eval_end])
        >= wf.MIN_EVAL_MONTHS
        for f in thin
    )


def test_folds_needs_a_sane_geometry():
    with pytest.raises(ValueError, match="at least 1"):
        wf.folds(M240, eval_years=0)


def test_too_short_a_curve_yields_no_folds():
    assert wf.folds([date(2000, 1, 1)]) == ()


# --------------------------------------------------------------------------- measure

def test_measure_reports_the_slice_and_nothing_outside_it():
    ms = months(date(2000, 1, 1), 36)
    c = curve(ms, 0.01)
    got = wf.measure(c, ms[12], ms[24])
    assert got.months == 13
    assert got.total_return == pytest.approx(1.01 ** 12 - 1)
    assert got.max_drawdown == pytest.approx(0.0)


def test_measure_finds_the_worst_fall_inside_the_slice():
    ms = months(date(2000, 1, 1), 5)
    c = [(ms[0], 1.0), (ms[1], 1.2), (ms[2], 0.6), (ms[3], 0.9), (ms[4], 1.1)]
    got = wf.measure(c, ms[0], ms[4])
    assert got.max_drawdown == pytest.approx(0.5)  # 1.2 -> 0.6


def test_measure_returns_nothing_for_a_slice_with_one_point():
    ms = months(date(2000, 1, 1), 5)
    assert wf.measure(curve(ms, 0.01), ms[2], ms[2]) is None


def test_measure_strips_deposits_so_a_book_that_earned_nothing_reads_as_nothing():
    """The defect that bit lab regime, pinned here before walk-forward can inherit it."""
    ms = months(date(2000, 1, 1), 13)
    c = [(d, 100.0 + 10.0 * i) for i, d in enumerate(ms)]
    dep = {d: 10.0 for d in ms[1:]}
    assert wf.measure(c, ms[0], ms[-1], dep).total_return == pytest.approx(0.0, abs=1e-12)
    # and without the deposits it looks like a winner, which is the whole point
    assert wf.measure(c, ms[0], ms[-1]).total_return == pytest.approx(1.2)


# --------------------------------------------------------------------------- pick and evaluate

def test_the_pick_is_made_on_training_data_only():
    """A variant that is best on train must be chosen even when it is worst afterwards."""
    ms = months(date(1996, 1, 1), 240)
    good_then_bad = curve(ms[:132], 0.02) + curve(ms[132:], -0.01, start=curve(ms[:132], 0.02)[-1][1])
    steady = curve(ms, 0.005)
    chosen, mar = wf.pick({"A-GOOD-THEN-BAD": good_then_bad, "B-STEADY": steady},
                          wf.folds(ms)[0], ms[0])
    assert chosen == "A-GOOD-THEN-BAD"
    assert mar is not None


def test_a_method_that_wins_on_average_and_loses_every_fold_is_caught():
    """The case the whole plan exists for."""
    ms = months(date(1996, 1, 1), 240)
    # Enormous early run, then permanently behind the benchmark.
    early = curve(ms[:120], 0.03)
    book = early + curve(ms[120:], 0.001, start=early[-1][1])
    bench = curve(ms, 0.006)
    rec = wf.Record("M9999", wf.evaluate({"M9999-A": book}, bench, wf.folds(ms)))
    assert rec.won == 0
    assert not rec.majority
    # and it still beats the benchmark over the whole window, which is what hid it
    assert book[-1][1] > bench[-1][1]


def test_a_method_that_keeps_winning_reads_as_a_majority():
    ms = months(date(1996, 1, 1), 240)
    rec = wf.Record("M0001", wf.evaluate({"M0001-A": curve(ms, 0.012)}, curve(ms, 0.006),
                                         wf.folds(ms)))
    assert rec.won == len(rec.scored) > 0
    assert rec.majority and rec.stable


def _pick(fold_index: int, name: str, beat: bool) -> wf.FoldPick:
    """A FoldPick with a known winner, for testing the record rather than the curve maths."""
    f = wf.Fold(fold_index, date(2006, 1, 1), date(2006, 1, 28), date(2008, 12, 28))
    mine = wf.Slice(36, 0.5 if beat else 0.01, 0.1, 0.1, 1.0)
    theirs = wf.Slice(36, 0.2, 0.06, 0.1, 0.6)
    return wf.FoldPick(f, name, 1.0, mine, theirs)


def test_an_unstable_record_says_the_choice_between_variants_is_noise():
    """The lab spends its one look on whichever variant ranks best on the last day. If that
    changes fold to fold, the choice between them is noise and the record must say so."""
    rec = wf.Record("M0002", (_pick(1, "M-A", True), _pick(2, "M-B", True)))
    assert not rec.stable
    assert "pick changed" in rec.summary()


def test_a_record_that_keeps_one_variant_is_stable():
    rec = wf.Record("M0002", (_pick(1, "M-A", True), _pick(2, "M-A", False)))
    assert rec.stable
    assert rec.summary() == "1 of 2 folds"


def test_a_record_needs_more_than_half_to_claim_a_majority():
    assert not wf.Record("M", (_pick(1, "A", True), _pick(2, "A", False))).majority
    assert wf.Record("M", (_pick(1, "A", True), _pick(2, "A", True),
                           _pick(3, "A", False))).majority


def test_evaluate_on_no_candidates_is_empty_not_an_error():
    assert wf.evaluate({}, curve(M240, 0.005), wf.folds(M240)) == ()


# --------------------------------------------------------------------------- the buy signal

def winner() -> wf.Record:
    ms = months(date(1996, 1, 1), 240)
    return wf.Record("M0001", wf.evaluate({"M0001-A": curve(ms, 0.012)},
                                          curve(ms, 0.006), wf.folds(ms)))


def loser() -> wf.Record:
    ms = months(date(1996, 1, 1), 240)
    return wf.Record("M0002", wf.evaluate({"M0002-A": curve(ms, 0.002)},
                                          curve(ms, 0.006), wf.folds(ms)))


def test_buy_signal_needs_all_three():
    assert wf.buy_signal(True, winner(), 0.03)[0] is True


def test_buy_signal_refuses_a_method_the_lab_has_not_cleared():
    fired, why = wf.buy_signal(False, winner(), 0.03)
    assert fired is False and "not dev-eligible" in why


def test_buy_signal_refuses_a_good_average_that_loses_the_folds():
    fired, why = wf.buy_signal(True, loser(), 0.03)
    assert fired is False and "fails the folds" in why


def test_buy_signal_refuses_an_edge_that_dies_where_the_data_is_best():
    """The condition that makes the purchase about data rather than enthusiasm."""
    fired, why = wf.buy_signal(True, winner(), -0.021)
    assert fired is False and "negative 2009-2015 edge" in why


def test_buy_signal_refuses_when_the_era_edge_was_never_measured():
    fired, why = wf.buy_signal(True, winner(), None)
    assert fired is False and "never" not in why and "no 2009-2015 edge" in why


def test_buy_signal_says_what_it_cleared_so_a_report_can_quote_it():
    fired, why = wf.buy_signal(True, winner(), 0.026)
    assert fired and "dev-eligible" in why and "folds" in why and "+2.6" in why


def test_a_slice_that_never_fell_ranks_above_one_that_did():
    """Zero drawdown is infinite return per unit of fall, not an unrankable candidate."""
    ms = months(date(2000, 1, 1), 24)
    smooth = wf.measure(curve(ms, 0.01), ms[0], ms[-1])
    assert smooth.max_drawdown == pytest.approx(0.0)
    assert smooth.mar == float("inf")
    bumpy = [(d, v) for d, v in curve(ms, 0.01)]
    bumpy[10] = (bumpy[10][0], bumpy[10][1] * 0.8)
    assert wf.measure(bumpy, ms[0], ms[-1]).mar < smooth.mar


def test_a_losing_slice_that_never_fell_cannot_happen_but_is_ranked_last_anyway():
    ms = months(date(2000, 1, 1), 3)
    flat = [(ms[0], 1.0), (ms[1], 1.0), (ms[2], 1.0)]
    got = wf.measure(flat, ms[0], ms[-1])
    assert got.max_drawdown == pytest.approx(0.0)
    assert got.mar == float("-inf")


def test_buy_signal_refuses_a_family_that_has_already_failed_out_of_sample():
    """Found by running it: all three firings were in families already disproven.

    A status column is not the evidence. M0007 read dev-eligible only because no formal look had
    been spent on it, while its own realistic twin had lost to a deposit-matched SPY.
    """
    fired, why = wf.buy_signal(True, winner(), 0.03, family_failed="M0022")
    assert fired is False
    assert "family already failed" in why and "M0022" in why


def test_the_family_check_does_not_block_a_clean_family():
    assert wf.buy_signal(True, winner(), 0.03, family_failed=None)[0] is True
