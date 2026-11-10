"""M0538's sort: the loser pick must hold the lowest scores (M0537 held the highest)."""

from seer_engine.lab.methods.m0538_loser_reversal_five_draws import pick_extreme


def test_loser_pick_is_the_lowest_scores():
    scores = {"A": 0.30, "B": -0.20, "C": 0.05, "D": -0.45, "E": 0.10}
    assert pick_extreme(scores, "loser", 2) == ["D", "B"]


def test_ties_break_on_symbol():
    assert pick_extreme({"Z": -1.0, "A": -1.0, "M": 0.0}, "loser", 1) == ["A"]
