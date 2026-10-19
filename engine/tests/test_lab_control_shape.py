"""The control-shape check (lab/control_shape.py): detection, resolution, and the band.

Two fixtures, deliberately:

- **stubs and a temp lab** for every rule. The band's edges (0.80, 1.25, 0.50, 2.00) have no
  recorded arm sitting on them, so the committed lab cannot exercise them at all; and the
  committed lab grows, so a rule pinned to its contents would go red when a method lands rather
  than when the rule changes.
- **the committed lab/lab.sqlite** for the calibration table, because it IS the evidence the band
  was cut from. The twelve arms named below are frozen rows (trials_no_update, trials_no_delete);
  nothing else about the database is asserted, so a growing lab leaves this test alone.

The committed database is opened mode=ro and never through store.connect, which migrates and so
dirties the file on a read. The calibration test hashes it before and after and asserts it did
not move.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

import pytest

from seer_engine.lab import control_shape as cs
from seer_engine.lab import store

# ------------------------------------------------------------------ stubs


@dataclass(frozen=True)
class Stub:
    """An arm as this module sees one: an id and one line of prose."""

    id: str
    rationale: str


@dataclass(frozen=True)
class Declaring:
    """A stub that names the arm it controls, the way a future Candidate field will."""

    id: str
    rationale: str
    controls: str


# The real rationales, quoted from the method files on 2026-10-19. They are frozen records, so a
# literal here can never drift from the file without the file's own freeze test going red first.
R_ALL_R = "The same composite with linear rank weights: does conviction in the top names pay"
R_RAND1 = "Control: the same day's scores handed to hash-drawn names, power 1"
R_CORE = "The yardstick: 50 biggest members at market value, 10% ceiling, no tilt"
R_C50 = "The idea: 50% SPY + 50% in the 20 biggest shrinkers, equal slots, nothing timed"
R_C50_R = "Placebo: the same frame with 20 hash-drawn names from the same scored pool"
R_STALE = "split one to two years ago and not since: the dose-response control on the date itself"
R_STALE30 = "newest gesture one to two years old and none since: does the date do any work?"
R_B100 = (
    "Within-frame control: pure buyback intensity, the 20 biggest one-year share-count shrinkers "
    "in the pool, no discount information"
)
R_PLAIN = "the 30 members whose newest gesture of any of the four kinds is the most recent"


# ------------------------------------------------------------------ (1) detection


def test_every_marker_is_lowercase_so_it_can_actually_fire():
    """kind_of lowercases the rationale; a mixed-case marker would match nothing, ever."""
    for group in (cs.DOSE_MARKERS, cs.DRAW_MARKERS, cs.ABLATION_MARKERS, cs.IDEA_MARKERS):
        for marker in group:
            assert marker == marker.lower(), f"{marker!r} can never match a lowercased rationale"
            assert marker.strip() == marker and marker, f"{marker!r} is padded or empty"


def test_a_rank_weighting_variant_is_not_a_control_despite_its_suffix():
    """M0005-ALL-R: the whole argument for reading the rationale instead of the id.

    An id-suffix rule calls it a control, measures it against M0005-ALL, finds 1.00x/1.07x and
    passes -- so the misclassification never surfaces and the next -R that is a real variant is
    judged the same wrong way.
    """
    assert cs.kind_of(Stub("M0005-ALL-R", R_ALL_R)) == cs.KIND_NONE


def test_the_three_kinds_come_out_of_the_three_marker_tables():
    assert cs.kind_of(Stub("M0222-RAND1", R_RAND1)) == cs.KIND_PLACEBO
    assert cs.kind_of(Stub("M0230-C50-R", R_C50_R)) == cs.KIND_PLACEBO
    assert cs.kind_of(Stub("M0244-STALE30", R_STALE30)) == cs.KIND_DOSE
    assert cs.kind_of(Stub("M0248-B100", R_B100)) == cs.KIND_ABLATION
    assert cs.kind_of(Stub("M0244-FRESH30", R_PLAIN)) == cs.KIND_NONE


def test_dose_is_tested_before_draw_so_a_dose_arm_is_never_a_placebo():
    """M0241-STALE's rationale carries the word 'control'; a dose arm must never be shape-checked.

    The ordering is the guard against the single worst outcome available here -- a permanent false
    alarm on a correct arm -- and it is asserted on a sentence that carries both marks at once.
    """
    assert cs.kind_of(Stub("M0241-STALE", R_STALE)) == cs.KIND_DOSE
    both = Stub("M9999-X", "Placebo: the same names at a one-to-two-year dose-response spacing")
    assert cs.kind_of(both) == cs.KIND_DOSE


def test_a_declaration_is_read_duck_typed_and_absent_everywhere_today():
    assert cs.declared_target(Stub("M9999-R", R_C50_R)) is None
    assert cs.declared_target(Declaring("M9999-R", R_C50_R, "M9999-CORE")) == "M9999-CORE"
    assert cs.declared_target(Declaring("M9999-R", R_C50_R, "   ")) is None


# ------------------------------------------------------------------ (2) the ladder


def test_rung_one_is_a_declaration_and_it_outranks_every_other_rung():
    arms = [
        Stub("M9999-CORE", R_CORE),
        Stub("M9999-TILT", R_PLAIN),
        Declaring("M9999-TILT-R", R_C50_R, "M9999-TILT"),
    ]
    assert cs.resolve_target(arms[2], arms) == ("M9999-TILT", cs.RUNG_DECLARED)


def test_rung_two_is_the_sibling_the_id_stems_to():
    arms = [Stub("M0230-C50", R_C50), Stub("M0230-C50-R", R_C50_R)]
    assert cs.resolve_target(arms[1], arms) == ("M0230-C50", cs.RUNG_STEM)


def test_rung_three_is_the_arm_that_calls_itself_the_idea_or_the_yardstick():
    """M0248's idea is candidate [2], not [0]: position is not the rule, the rationale is."""
    arms = [
        Stub("M0248-B100", R_B100),
        Stub("M0248-B75", R_PLAIN),
        Stub("M0248-EQ", "The idea: equal parts buyback intensity and discount from the high"),
        Stub("M0248-R", "Placebo: 20 names from the identical pool in a monthly-redrawn hash order"),
    ]
    assert cs.resolve_target(arms[3], arms) == ("M0248-EQ", cs.RUNG_IDEA)


def test_rung_four_is_the_first_declared_arm_and_says_so():
    arms = [
        Stub("M0244-FRESH30", R_PLAIN),
        Stub("M0244-STALE30", R_STALE30),
        Stub("M0244-PLACEBO30", "FRESH30's count, cohort composition and turnover, hash-drawn names"),
    ]
    assert cs.resolve_target(arms[2], arms) == ("M0244-FRESH30", cs.RUNG_FIRST)


def test_no_rung_ever_resolves_one_control_against_another():
    """M0193/M0187/M0207 are methods whose every arm is a placebo.

    Without this exclusion the ladder reported M0193-S1-SW as a 13.7x refusal against M0193-S1 --
    two placebos, neither controlling the other. Sixteen such false refusals, measured 2026-10-19.
    """
    arms = [
        Stub("M0193-S1", "the sticky placebo: one hash order drawn once and held"),
        Stub("M0193-S1-SW", "the sticky placebo behind the switch, one hash order"),
    ]
    assert cs.resolve_target(arms[1], arms) == (None, None)


def test_a_dose_arm_is_not_an_eligible_target_either():
    arms = [
        Stub("M0243-NEAR20", R_PLAIN),
        Stub("M0243-NEAR20-T3", "A stricter dose: the 20 biggest shrinkers inside the near THIRD"),
        Stub("M0243-NEAR20-R", "Placebo: 20 names from the identical near half in a hash order"),
    ]
    assert cs.resolve_target(arms[2], arms) == ("M0243-NEAR20", cs.RUNG_STEM)


def test_an_ablation_stays_an_eligible_target():
    """A within-frame control is a signal arm, so comparing a placebo with it is legitimate."""
    arms = [Stub("M9999-B100", R_B100), Stub("M9999-R", R_C50_R)]
    assert cs.resolve_target(arms[1], arms) == ("M9999-B100", cs.RUNG_FIRST)


# ------------------------------------------------------------------ (3) the band


def test_the_bands_are_log_symmetric():
    """Trading twice as much and half as much are the same sin."""
    assert cs.WARN_BAND[1] == pytest.approx(1.0 / cs.WARN_BAND[0])
    assert cs.REFUSE_BAND[1] == pytest.approx(1.0 / cs.REFUSE_BAND[0])
    assert cs.REFUSE_BAND[0] < cs.WARN_BAND[0] < 1.0 < cs.WARN_BAND[1] < cs.REFUSE_BAND[1]


def test_the_band_edges_are_inclusive():
    assert cs.band_verdict(1.0) == cs.OK
    assert cs.band_verdict(0.80) == cs.OK
    assert cs.band_verdict(1.25) == cs.OK
    assert cs.band_verdict(0.79) == cs.WARN
    assert cs.band_verdict(1.26) == cs.WARN
    assert cs.band_verdict(0.50) == cs.WARN
    assert cs.band_verdict(2.00) == cs.WARN
    assert cs.band_verdict(0.49) == cs.REFUSE
    assert cs.band_verdict(2.01) == cs.REFUSE


def test_the_band_separates_the_measured_table_with_room_on_both_sides():
    """The evidence the constants were cut from, as numbers rather than as a claim.

    The widest gap in the measurement is 1.372 (M0241-PLACEBO, the one warn-only arm) to 2.976
    (M0243-NEAR20-R, the worst clean-side refusal). The refuse band sits inside it.
    """
    assert cs.band_verdict(1.015) == cs.OK and cs.band_verdict(0.984) == cs.OK
    assert cs.band_verdict(1.372) == cs.WARN and cs.band_verdict(1.131) == cs.OK
    assert cs.WARN_BAND[1] < 1.372 < cs.REFUSE_BAND[1] < 2.976


def test_the_worse_axis_wins_which_is_why_there_are_two():
    """M0226-RAND2: 1.330x trades is a warn, 14.528x turnover is a refusal."""
    assert cs.band_verdict(1.330) == cs.WARN
    assert cs.band_verdict(14.528) == cs.REFUSE
    assert cs.worst([cs.band_verdict(1.330), cs.band_verdict(14.528)]) == cs.REFUSE
    assert cs.worst([cs.OK, cs.OK]) == cs.OK
    assert cs.worst([]) == cs.OK
    assert cs.worst([cs.UNRESOLVED]) == cs.OK


# ------------------------------------------------------------------ a synthetic lab


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M9999", candidate_id="M9999-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="399d0d25", git_sha="abc123",
        run_at="2026-10-19T00:00:00+00:00", total_return=3.0, cagr=0.12, max_drawdown=0.11,
        profit_factor=1.6, trades=250, sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008,
        worst_year_return=-0.1, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="",
        eligible=True, dsr=0.97, n_trials_at_run=60, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _lab(conn, mid: str, rows: list[tuple[str, int, float | None]]) -> None:
    """One method and one dev trial per (candidate id, trades, turnover)."""
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family=mid, source_kind="knowledge",
                         hypothesis="h", status="registered")
        store.insert_trials(conn, [
            _trial(method_id=mid, candidate_id=cid, config_digest=f"d-{cid}",
                   trades=trades, turnover=turnover)
            for cid, trades, turnover in rows
        ])


def test_a_method_with_no_control_arm_produces_no_finding_rather_than_an_error(conn):
    _lab(conn, "M9001", [("M9001-A", 500, 2.0), ("M9001-B", 520, 2.1)])
    arms = [Stub("M9001-A", R_PLAIN), Stub("M9001-B", R_PLAIN)]
    assert cs.findings(conn, "M9001", arms) == ()


def test_both_axes_are_read_and_a_clean_trade_count_does_not_save_a_wild_turnover(conn):
    """The M0226-RAND2 shape, synthesised: 1682/1265 trades and 3.92/0.27 turnover."""
    _lab(conn, "M9002", [("M9002-CORE", 1265, 0.26991620735577115),
                         ("M9002-RAND2", 1682, 3.921436895717432)])
    arms = [Stub("M9002-CORE", R_CORE), Stub("M9002-RAND2", R_RAND1)]
    (f,) = cs.findings(conn, "M9002", arms)
    assert f.target_id == "M9002-CORE" and f.rung == cs.RUNG_IDEA
    assert round(f.trade_ratio, 3) == 1.330
    assert round(f.turnover_ratio, 3) == 14.528
    assert cs.band_verdict(f.trade_ratio) == cs.WARN
    assert f.verdict == cs.REFUSE and f.refused and f.flagged


def test_a_dose_arm_is_reported_and_never_shape_flagged(conn):
    _lab(conn, "M9003", [("M9003-FRESH", 2536, 11.67), ("M9003-STALE", 698, 3.57)])
    arms = [Stub("M9003-FRESH", R_PLAIN), Stub("M9003-STALE", R_STALE30)]
    (f,) = cs.findings(conn, "M9003", arms)
    assert f.kind == cs.KIND_DOSE
    assert f.verdict == cs.NOT_CHECKED
    assert f.target_id is None and f.trade_ratio is None and f.turnover_ratio is None
    assert not f.refused and not f.flagged


def test_an_unresolvable_control_never_refuses(conn):
    """Fail open on 'I cannot tell who this controls'; fail loud only on a measured mismatch."""
    _lab(conn, "M9004", [("M9004-S1", 15, 0.21), ("M9004-S1-SW", 206, 0.93)])
    arms = [
        Stub("M9004-S1", "the sticky placebo: one hash order drawn once and held"),
        Stub("M9004-S1-SW", "the sticky placebo behind the switch, one hash order"),
    ]
    found = cs.findings(conn, "M9004", arms)
    assert len(found) == 2
    assert {f.verdict for f in found} == {cs.UNRESOLVED}
    assert cs.refusals(found) == () and cs.flags(found) == ()


def test_a_control_with_no_recorded_trial_is_unrecorded_not_a_refusal(conn):
    _lab(conn, "M9005", [("M9005-CORE", 500, 2.0)])
    arms = [Stub("M9005-CORE", R_CORE), Stub("M9005-R", R_C50_R)]
    (f,) = cs.findings(conn, "M9005", arms)
    assert f.verdict == cs.UNRECORDED and f.target_id == "M9005-CORE"
    assert "M9005-R" in f.reason and not f.refused


def test_a_declared_target_that_names_no_arm_surfaces_instead_of_falling_through(conn):
    _lab(conn, "M9006", [("M9006-CORE", 500, 2.0), ("M9006-R", 505, 2.02)])
    arms = [Stub("M9006-CORE", R_CORE), Declaring("M9006-R", R_C50_R, "M9006-GHOST")]
    (f,) = cs.findings(conn, "M9006", arms)
    assert f.rung == cs.RUNG_DECLARED and f.target_id == "M9006-GHOST"
    assert f.verdict == cs.UNRECORDED


def test_a_zero_trade_target_leaves_that_axis_unmeasured_rather_than_infinite(conn):
    """Five recorded dev rows have trades = 0: a partial-weight book that still moves exposure."""
    _lab(conn, "M9007", [("M9007-CORE", 0, 2.0), ("M9007-R", 505, 2.02)])
    arms = [Stub("M9007-CORE", R_CORE), Stub("M9007-R", R_C50_R)]
    (f,) = cs.findings(conn, "M9007", arms)
    assert f.trade_ratio is None
    assert round(f.turnover_ratio, 3) == 1.010
    assert f.verdict == cs.OK


def test_neither_axis_measurable_is_unrecorded(conn):
    _lab(conn, "M9008", [("M9008-CORE", 0, 0.0), ("M9008-R", 505, 2.02)])
    arms = [Stub("M9008-CORE", R_CORE), Stub("M9008-R", R_C50_R)]
    (f,) = cs.findings(conn, "M9008", arms)
    assert f.verdict == cs.UNRECORDED and not f.refused


def test_nothing_is_written_by_asking(conn):
    _lab(conn, "M9009", [("M9009-CORE", 500, 2.0), ("M9009-R", 2000, 8.0)])
    arms = [Stub("M9009-CORE", R_CORE), Stub("M9009-R", R_C50_R)]
    before = (store.dev_trial_count(conn), store.test_looks(conn))
    cs.findings(conn, "M9009", arms)
    cs.format_report(cs.findings(conn, "M9009", arms))
    assert (store.dev_trial_count(conn), store.test_looks(conn)) == before


def test_the_report_names_the_band_the_rung_and_both_ratios(conn):
    _lab(conn, "M9010", [("M9010-CORE", 500, 2.0), ("M9010-R", 2000, 8.0)])
    arms = [Stub("M9010-CORE", R_CORE), Stub("M9010-R", R_C50_R)]
    found = cs.findings(conn, "M9010", arms)
    text = cs.format_report(found)
    assert "0.80" in text and "1.25" in text and "0.50" in text and "2.00" in text
    assert cs.RUNG_IDEA in text
    assert "4.00" in text
    assert cs.REFUSE in text
    assert "no control arm to report" in cs.format_report(())
    assert cs.describe(found[0]).startswith("M9010-R (against M9010-CORE, resolved by ")


def test_show_clean_false_keeps_only_what_must_be_acted_on(conn):
    """The shape the lab run annotation wants: a clean control prints nothing to read."""
    _lab(conn, "M9011", [("M9011-CORE", 500, 2.0), ("M9011-R", 505, 2.02)])
    arms = [Stub("M9011-CORE", R_CORE), Stub("M9011-R", R_C50_R)]
    found = cs.findings(conn, "M9011", arms)
    assert found[0].verdict == cs.OK
    assert "no control arm to report" in cs.format_report(found, show_clean=False)
    assert "M9011-R" in cs.format_report(found, show_clean=True)


# ------------------------------------------------------------------ supersession


def _declaring(stub, *ids):
    """``stub`` with a ``supersedes`` declaration on it, however ``Stub`` is built.

    ``control_shape`` reads the attribute duck-typed through ``SUPERSEDES_ATTR``, exactly as it
    reads ``DECLARATION_ATTR``, so a test arm declares by carrying the attribute and nothing in
    this module has to import ``backtest.dev``."""
    object.__setattr__(stub, cs.SUPERSEDES_ATTR, tuple(ids))
    return stub


def _finding(**kw) -> cs.Finding:
    """A Finding built by hand, for the one case `findings` cannot produce in a single method.

    An `unresolved` arm and a resolved refusal cannot coexist under one method id: `resolve_target`
    returns (None, None) only when the eligible set is empty, and an eligible set that is empty for
    one placebo is empty for all of them. So the predicate is exercised directly for that case.
    """
    base = dict(
        method_id="M9999", control_id="M9999-R", kind=cs.KIND_PLACEBO, target_id="M9999-CORE",
        rung=cs.RUNG_STEM, control=None, target=None, trade_ratio=1.0, turnover_ratio=1.0,
        verdict=cs.OK, reason="r", declares=(),
    )
    base.update(kw)
    return cs.Finding(**base)


def test_a_band_clean_placebo_that_declares_a_refused_one_supersedes_it(conn):
    """The whole point of the rule: an honest control retires the handicapped one it NAMES.

    The refusal is NOT dropped. Its verdict is still refuse, both ratios are still there and it is
    still flagged -- the sentence already written about its margin was quoted against a
    handicapped opponent and that stays readable. Only `blocking` goes false, and `refusals` --
    which is what `hardgate` acts on -- is what reads `blocking`.
    """
    _lab(conn, "M9020", [("M9020-CORE", 500, 2.0),
                         ("M9020-R", 35, 0.14),
                         ("M9020-CORE-PLC", 505, 2.02)])
    arms = [Stub("M9020-CORE", R_CORE), Stub("M9020-R", R_C50_R),
            _declaring(Stub("M9020-CORE-PLC", R_C50_R), "M9020-R")]
    found = cs.findings(conn, "M9020", arms)
    by_id = {f.control_id: f for f in found}

    old, new = by_id["M9020-R"], by_id["M9020-CORE-PLC"]
    assert old.verdict == cs.REFUSE and round(old.trade_ratio, 2) == 0.07
    assert new.verdict == cs.OK and new.superseded_by is None
    assert new.declares == ("M9020-R",)

    assert old.superseded_by == "M9020-CORE-PLC"
    assert old.superseded_by_target == new.target_id
    assert old.refused is True and old.flagged is True       # still reported, never dropped
    assert old.blocking is False                             # and no longer stopping a promotion
    assert cs.refusals(found) == ()
    assert old in cs.flags(found)
    assert "superseded by M9020-CORE-PLC" in cs.describe(old)


def test_a_clean_placebo_that_declares_nothing_supersedes_nothing(conn):
    """The condition that makes this a measured no-op on the committed lab, where no arm declares.

    It is also the half of the rule that replaced target equality: a well-shaped control of the
    same book is NOT evidence that it was drawn to replace the bent one, and before 2026-10-19
    nobody had ever been asked to say so.
    """
    _lab(conn, "M9027", [("M9027-CORE", 500, 2.0),
                         ("M9027-R", 35, 0.14),
                         ("M9027-CORE-PLC", 505, 2.02)])
    arms = [Stub("M9027-CORE", R_CORE), Stub("M9027-R", R_C50_R), Stub("M9027-CORE-PLC", R_C50_R)]
    found = cs.findings(conn, "M9027", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9027-CORE-PLC"].verdict == cs.OK          # same target, clean, declares nothing
    assert by_id["M9027-CORE-PLC"].target_id == by_id["M9027-R"].target_id
    assert by_id["M9027-R"].superseded_by is None
    assert [f.control_id for f in cs.refusals(found)] == ["M9027-R"]


def test_a_warn_superseder_does_not_supersede_even_when_it_declares(conn):
    """Measured on the committed lab: under an OK-or-WARN band M0047-PLC1-MV20 (0.545x) would
    retire M0047-PLC1-MV10 (0.549x) -- one bent stick replacing another, with no honest control
    drawn. The arm doing the retiring has to clear the MATCH band, not merely the refuse band."""
    _lab(conn, "M9021", [("M9021-CORE", 500, 2.0),
                         ("M9021-R", 35, 0.14),
                         ("M9021-CORE-PLC", 700, 2.8)])
    arms = [Stub("M9021-CORE", R_CORE), Stub("M9021-R", R_C50_R),
            _declaring(Stub("M9021-CORE-PLC", R_C50_R), "M9021-R")]
    found = cs.findings(conn, "M9021", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9021-CORE-PLC"].verdict == cs.WARN      # 1.40x: inside refuse, outside match
    assert by_id["M9021-R"].superseded_by is None
    assert [f.control_id for f in cs.refusals(found)] == ["M9021-R"]


def test_a_declared_supersession_crosses_a_different_target_on_purpose(conn):
    """The reason target equality was dropped, as a test rather than as an argument.

    `M9022-R` resolves to `M9022-CORE` -- the ladder's own guess. The arm drawn to replace it is
    named after its TRUE target and so resolves to `M9022-WIDE`. Under a target-equality rule
    nothing would be superseded and the method would stay blocked after all the measuring; under
    the declaration it is superseded, and BOTH targets are reported so the re-point is visible.
    """
    _lab(conn, "M9022", [("M9022-CORE", 500, 2.0),
                         ("M9022-WIDE", 900, 3.6),
                         ("M9022-R", 35, 0.14),
                         ("M9022-WIDE-PLC", 909, 3.64)])
    arms = [Stub("M9022-CORE", R_CORE), Stub("M9022-WIDE", R_PLAIN),
            Stub("M9022-R", R_C50_R),
            _declaring(Stub("M9022-WIDE-PLC", R_C50_R), "M9022-R")]
    found = cs.findings(conn, "M9022", arms)
    by_id = {f.control_id: f for f in found}
    old, new = by_id["M9022-R"], by_id["M9022-WIDE-PLC"]
    assert old.target_id == "M9022-CORE" and new.target_id == "M9022-WIDE"
    assert new.verdict == cs.OK
    assert old.superseded_by == "M9022-WIDE-PLC"
    assert old.superseded_by_target == "M9022-WIDE"
    assert cs.refusals(found) == ()
    said = cs.describe(old)
    assert "M9022-WIDE-PLC" in said and "M9022-WIDE" in said and "M9022-CORE" in said
    assert "M9022-WIDE-PLC -> M9022-WIDE" in cs.format_report(found)


def test_one_clean_arm_does_not_excuse_a_sibling_it_did_not_name(conn):
    """The other half of why target equality went. `M0215-HASH` and `M0215-HASH-CAP4` both resolve
    to `M0215-CTRL`, so under equality one honest control of CTRL would excuse an arm whose job is
    to price what a cap does and which was never scored against CTRL in spirit. Each old arm is
    retired by the arm that names it, and by no other."""
    _lab(conn, "M9028", [("M9028-CORE", 500, 2.0),
                         ("M9028-R", 35, 0.14),
                         ("M9028-R2", 36, 0.15),
                         ("M9028-CORE-PLC", 505, 2.02)])
    arms = [Stub("M9028-CORE", R_CORE), Stub("M9028-R", R_C50_R), Stub("M9028-R2", R_C50_R),
            _declaring(Stub("M9028-CORE-PLC", R_C50_R), "M9028-R")]
    found = cs.findings(conn, "M9028", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9028-R"].target_id == by_id["M9028-R2"].target_id == "M9028-CORE"
    assert by_id["M9028-R"].superseded_by == "M9028-CORE-PLC"
    assert by_id["M9028-R2"].superseded_by is None
    assert [f.control_id for f in cs.refusals(found)] == ["M9028-R2"]


def test_a_warn_arm_is_superseded_too_although_it_never_blocked(conn):
    """`M0047-PLC1-MV20` is the lab's one such arm: 0.545x / 0.508x, inside the refuse band and
    outside the match band. It stops no promotion, so retiring it moves no gate -- but every
    margin written against it is as little evidence as its refused twin's, and leaving one of a
    re-drawn pair unmarked would tell a reader the opposite."""
    _lab(conn, "M9029", [("M9029-CORE", 500, 2.0),
                         ("M9029-W", 350, 1.40),
                         ("M9029-CORE-PLC", 505, 2.02)])
    arms = [Stub("M9029-CORE", R_CORE), Stub("M9029-W", R_C50_R),
            _declaring(Stub("M9029-CORE-PLC", R_C50_R), "M9029-W")]
    found = cs.findings(conn, "M9029", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9029-W"].verdict == cs.WARN
    assert by_id["M9029-W"].superseded_by == "M9029-CORE-PLC"
    assert by_id["M9029-W"].blocking is False
    assert by_id["M9029-W"] in cs.flags(found)               # still a "read this" row
    assert cs.refusals(found) == ()


def test_an_unrecorded_or_unresolved_sibling_never_supersedes(conn):
    """Absence is not evidence (D16's sentence), and this is the case that matters in practice.

    A re-drawn control is committed to the method file BEFORE it is run -- the commit is the
    pre-registration. Between that commit and the run the new arm has no trial row, so its finding
    is `unrecorded`. If that superseded, the gate would clear on the intention rather than on the
    measurement, and the whole pre-registration discipline would be bypassable by writing a
    docstring.
    """
    _lab(conn, "M9023", [("M9023-CORE", 500, 2.0), ("M9023-R", 35, 0.14)])
    arms = [Stub("M9023-CORE", R_CORE), Stub("M9023-R", R_C50_R),
            _declaring(Stub("M9023-CORE-PLC", R_C50_R), "M9023-R")]
    found = cs.findings(conn, "M9023", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9023-CORE-PLC"].verdict == cs.UNRECORDED
    assert by_id["M9023-R"].superseded_by is None
    assert [f.control_id for f in cs.refusals(found)] == ["M9023-R"]

    bent = _finding(method_id="M9023", control_id="M9023-R", verdict=cs.REFUSE,
                    trade_ratio=0.07, turnover_ratio=0.07, target_id="M9023-CORE")
    unresolved = _finding(method_id="M9023", control_id="M9023-S", verdict=cs.UNRESOLVED,
                          target_id=None, rung=None, trade_ratio=None, turnover_ratio=None)
    assert cs.superseding_arm(bent, (bent, unresolved)) is None


def test_a_dose_response_sibling_never_supersedes(conn):
    """A dose arm carries no ratio at all, so it is nobody's measuring stick.

    If it superseded, `kind_of`'s dose-before-draw ordering would become the way to clear D17: word
    the re-drawn control as a dose and the refusal disappears with nothing measured. The ordering
    exists to protect a correct arm from a false alarm, not to hand out a bypass.
    """
    _lab(conn, "M9024", [("M9024-CORE", 500, 2.0),
                         ("M9024-R", 35, 0.14),
                         ("M9024-STALE", 505, 2.02)])
    arms = [Stub("M9024-CORE", R_CORE), Stub("M9024-R", R_C50_R),
            _declaring(Stub("M9024-STALE", R_STALE30), "M9024-R")]
    found = cs.findings(conn, "M9024", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9024-STALE"].kind == cs.KIND_DOSE
    assert by_id["M9024-STALE"].verdict == cs.NOT_CHECKED
    assert by_id["M9024-R"].superseded_by is None
    assert [f.control_id for f in cs.refusals(found)] == ["M9024-R"]
    # And a shape-matched arm that is not a control at all (M9024-CORE itself) produces no
    # finding, so it cannot supersede either.
    assert "M9024-CORE" not in by_id


def test_a_superseded_arm_stays_in_the_report_with_its_ratios(conn):
    """Still reported, never dropped -- in both the full report and the act-on-this-only one."""
    _lab(conn, "M9025", [("M9025-CORE", 500, 2.0),
                         ("M9025-R", 35, 0.14),
                         ("M9025-CORE-PLC", 505, 2.02)])
    arms = [Stub("M9025-CORE", R_CORE), Stub("M9025-R", R_C50_R),
            _declaring(Stub("M9025-CORE-PLC", R_C50_R), "M9025-R")]
    found = cs.findings(conn, "M9025", arms)

    text = cs.format_report(found)
    assert "M9025-R" in text and "0.07" in text and cs.REFUSE in text
    assert "superseded by" in text and "M9025-CORE-PLC" in text
    assert "has to stay readable" in text

    loud = cs.format_report(found, show_clean=False)
    assert "M9025-R" in loud and "superseded by" in loud


def test_the_report_grows_no_column_when_nothing_is_superseded(conn):
    """Sixty-four rows of dashes to carry information in none of them is noise, so the column
    appears only when it says something, and today's report is unchanged."""
    _lab(conn, "M9026", [("M9026-CORE", 500, 2.0), ("M9026-R", 2000, 8.0)])
    arms = [Stub("M9026-CORE", R_CORE), Stub("M9026-R", R_C50_R)]
    assert "superseded by" not in cs.format_report(cs.findings(conn, "M9026", arms))


# ------------------------------------------------------------------ the calibration table


def _committed_lab():
    """A read-only connection to the committed lab, or None when this tree has no database.

    store.COMMITTED_DB and not SEER_LAB_DB: in a sera worktree the shared database holds sibling
    methods this tree's files do not have. Raw sqlite3 with mode=ro, never store.connect, which
    migrates on connect and so dirties the committed file on a read.
    """
    if not store.COMMITTED_DB.exists():
        return None
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# control id -> (kind, target id, rung, trades x, turnover x, verdict), measured 2026-10-19
# against the arm the ladder resolves -- NOT against the nearest sibling by trade ratio, which is
# what the analysis document's table used and which is not the arm being controlled.
CALIBRATION: dict[str, tuple[str, str | None, str | None, float | None, float | None, str]] = {
    "M0222-RAND1": (cs.KIND_PLACEBO, "M0222-CORE", cs.RUNG_IDEA, 0.984, 4.451, cs.REFUSE),
    "M0222-RAND2": (cs.KIND_PLACEBO, "M0222-CORE", cs.RUNG_IDEA, 1.063, 8.856, cs.REFUSE),
    "M0226-RAND1": (cs.KIND_PLACEBO, "M0226-CORE", cs.RUNG_IDEA, 0.979, 6.934, cs.REFUSE),
    "M0226-RAND2": (cs.KIND_PLACEBO, "M0226-CORE", cs.RUNG_IDEA, 1.330, 14.528, cs.REFUSE),
    "M0230-C50-R": (cs.KIND_PLACEBO, "M0230-C50", cs.RUNG_STEM, 0.067, 0.138, cs.REFUSE),
    "M0241-PLACEBO": (cs.KIND_PLACEBO, "M0241-SPLIT12", cs.RUNG_FIRST, 1.372, 1.131, cs.WARN),
    "M0241-STALE": (cs.KIND_DOSE, None, None, None, None, cs.NOT_CHECKED),
    "M0243-NEAR20-R": (cs.KIND_PLACEBO, "M0243-NEAR20", cs.RUNG_STEM, 3.013, 2.976, cs.REFUSE),
    "M0244-PLACEBO30": (cs.KIND_PLACEBO, "M0244-FRESH30", cs.RUNG_FIRST, 1.015, 0.984, cs.OK),
    "M0244-STALE30": (cs.KIND_DOSE, None, None, None, None, cs.NOT_CHECKED),
    "M0248-R": (cs.KIND_PLACEBO, "M0248-EQ", cs.RUNG_IDEA, 3.180, 3.078, cs.REFUSE),
}

CALIBRATION_METHODS: tuple[str, ...] = (
    "M0005", "M0222", "M0226", "M0230", "M0241", "M0243", "M0244", "M0248",
)


def test_the_calibration_table_is_what_the_code_computes():
    """Every row of the measured table, pinned, and the committed file unmoved afterwards.

    This is the band's evidence, not a code path: it asserts the constants still separate the
    measurement they were cut from. M0230-C50-R and M0248-R refuse -- the two cases the handover
    named. M0243-NEAR20-R refuses too, which the handover did not know about: the check finds a
    third. M0244-PLACEBO30 passes clean and M0241-PLACEBO warns alone.
    """
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    try:
        found = {f.control_id: f for f in cs.survey(conn, CALIBRATION_METHODS)}
    finally:
        conn.close()
    after = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    assert after == before, "reading the committed lab moved its bytes"

    assert "M0005-ALL-R" not in found, "a rank-weighting variant was read as a control"

    for control_id, expected in CALIBRATION.items():
        if control_id not in found:
            pytest.skip(f"{control_id} is not in this tree's lab database")
        f = found[control_id]
        kind, target, rung, trades, turnover, verdict = expected
        actual = (
            f.kind,
            f.target_id,
            f.rung,
            None if f.trade_ratio is None else round(f.trade_ratio, 3),
            None if f.turnover_ratio is None else round(f.turnover_ratio, 3),
            f.verdict,
        )
        assert actual == expected, f"{control_id}: {actual} != {expected}"


def test_the_two_cases_the_handover_named_refuse_and_the_third_one_does_too():
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    try:
        found = {f.control_id: f for f in cs.survey(conn, CALIBRATION_METHODS)}
    finally:
        conn.close()
    for control_id in ("M0230-C50-R", "M0248-R", "M0243-NEAR20-R"):
        if control_id not in found:
            pytest.skip(f"{control_id} is not in this tree's lab database")
        assert found[control_id].refused, f"{control_id} should refuse"
    for control_id in ("M0244-PLACEBO30",):
        if control_id not in found:
            pytest.skip(f"{control_id} is not in this tree's lab database")
        assert found[control_id].verdict == cs.OK, f"{control_id} should be clean"


def test_no_recorded_dose_arm_anywhere_in_the_lab_is_ever_shape_flagged():
    """An invariant over the whole lab, not a pin: a correct arm must never raise an alarm."""
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    try:
        found = cs.survey(conn)
    finally:
        conn.close()
    for f in found:
        if f.kind == cs.KIND_DOSE:
            assert f.verdict == cs.NOT_CHECKED and not f.flagged, f"{f.control_id} was flagged"


def test_nothing_refuses_without_both_a_resolved_target_and_a_measured_ratio():
    """The fail-open rule, asserted over every control arm the lab holds."""
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    try:
        found = cs.survey(conn)
    finally:
        conn.close()
    assert found, "the committed lab holds control arms; the survey found none"
    for f in found:
        if not f.refused:
            continue
        assert f.kind == cs.KIND_PLACEBO
        assert f.target_id is not None and f.rung is not None
        measured = [r for r in (f.trade_ratio, f.turnover_ratio) if r is not None]
        assert measured, f"{f.control_id} refuses on no measured axis"
        assert any(cs.band_verdict(r) == cs.REFUSE for r in measured)


# ------------------------------------------------------------------ the nine D17 blocks

# The thirteen refuse-band control arms the committed lab holds across the nine dev-eligible
# methods D17 stops, re-derived read-only on 2026-10-19 and matching `lab control` to the second
# decimal. These rows are frozen (trials_no_update, trials_no_delete), so the ratios can never
# move; the method files that name the arms are append-only in practice for the same reason.
BLOCKED_NINE: dict[str, tuple[tuple[str, str, float, float], ...]] = {
    "M0047": (("M0047-PLC1-MV10", "M0047-EQ", 0.549, 0.496),),
    "M0201": (("M0201-PLC1-MV10", "M0201-Y20-MV10", 2.266, 2.135),
              ("M0201-PLC2-MV10", "M0201-Y20-MV10", 2.261, 2.117)),
    "M0202": (("M0202-PLC1-HALF", "M0202-Y20-HALF", 2.248, 2.005),
              ("M0202-PLC2-HALF", "M0202-Y20-HALF", 2.245, 1.993),
              ("M0202-PLC1-HALF-FAST", "M0202-Y20-HALF", 2.248, 2.200)),
    "M0208": (("M0208-HASH-N20", "M0208-CGO-N20", 4.405, 5.197),),
    "M0215": (("M0215-HASH", "M0215-CTRL", 0.339, 0.428),
              ("M0215-HASH-CAP4", "M0215-CTRL", 0.339, 0.429)),
    "M0221": (("M0221-R50", "M0221-C50", 0.211, 0.498),),
    "M0225": (("M0225-R50", "M0225-C50", 0.195, 0.424),),
    "M0227": (("M0227-R20", "M0227-S20", 0.067, 0.117),),
    "M0243": (("M0243-NEAR20-R", "M0243-NEAR20", 3.013, 2.976),),
}


def test_supersession_moves_no_verdict_on_the_committed_lab():
    """The no-op proof, at the finding level: every one of the thirteen still reads `refuse`.

    This is the half of the rule that is true forever. `superseded_by` narrows what a GATE acts on;
    it never moves a verdict and never removes a row, because the old draw is the record of what
    every margin written against it was worth. A refusal that vanished from the report would be an
    amnesty, and this assertion is what stops one being written by accident.
    """
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    try:
        found = cs.survey(conn, tuple(BLOCKED_NINE))
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before

    by_id = {f.control_id: f for f in found}
    for mid, arms in BLOCKED_NINE.items():
        for control_id, target_id, trades, turnover in arms:
            if control_id not in by_id:
                pytest.skip(f"{control_id} is not in this tree's lab database")
            f = by_id[control_id]
            assert (f.method_id, f.kind, f.target_id) == (mid, cs.KIND_PLACEBO, target_id)
            assert f.verdict == cs.REFUSE, f"{control_id} is no longer reported as a refusal"
            assert round(f.trade_ratio, 3) == trades
            assert round(f.turnover_ratio, 3) == turnover


def test_nothing_in_the_committed_lab_is_superseded_today():
    """The no-op proof, lab-wide: on this tree's database the rule retires nothing at all.

    Measured 2026-10-19 over every method file: 64 findings, 19 refusals, 0 supersessions, before
    the change and after it. The nine blocked methods stay blocked until an honest control is drawn
    and RUN -- a committed-but-unrun amendment reads `unrecorded` and never supersedes, which is
    why this stays true for the whole of the 2026-10-19 plan set and flips only once phase 8 stages
    the new trials into lab/lab.sqlite.
    """
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    try:
        found = cs.survey(conn)
    finally:
        conn.close()
    assert found, "the committed lab holds control arms; the survey found none"
    for f in found:
        if f.superseded_by is None:
            continue
        honest = {g.control_id: g for g in found}[f.superseded_by]
        assert honest.verdict == cs.OK
        assert honest.kind == cs.KIND_PLACEBO
        assert honest.target_id == f.target_id
        assert honest.method_id == f.method_id
    assert cs.refusals(found) == tuple(f for f in found if f.verdict == cs.REFUSE), (
        "supersession retired a refusal on the committed lab; it must retire none until an "
        "honestly shaped control has been drawn, DECLARED and run"
    )
    # Until 2026-10-19 the stronger reason for the no-op was that NO arm declared anything at
    # all. That stopped being true the moment the 2026-10-19 plan set's own amendment blocks
    # landed in the method files, which is the work this rule exists to make count -- so the
    # claim that survives is the one above: nothing is RETIRED, because a declared-but-unrun arm
    # reads `unrecorded` and never supersedes. What is checked here instead is forever-true and
    # is the hazard the old assertion could not see: a declaration that names an arm which does
    # not exist, or belongs to another method, or was never flagged, is a typo that would
    # silently retire nothing and be found only in phase 8.
    by_id = {g.control_id: g for g in found}
    for f in found:
        for named in f.declares:
            g = by_id.get(named)
            assert g is not None, (
                f"{f.control_id} declares it supersedes {named}, which is not a control arm of "
                f"any method in this lab"
            )
            assert g.method_id == f.method_id, (
                f"{f.control_id} declares {named}, which belongs to {g.method_id}: a supersession "
                f"only ever reaches inside one method"
            )
            assert g.flagged, (
                f"{f.control_id} declares {named}, which is {g.verdict}: there is nothing to "
                f"retire, so the declaration is pointed at the wrong arm"
            )


def test_every_blocked_method_keeps_a_d17_reading_either_way():
    """Forever-true: each of the nine either still blocks, or holds the honest control that
    retired it -- never neither, and never a refusal that simply disappeared."""
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    try:
        found = cs.survey(conn, tuple(BLOCKED_NINE))
    finally:
        conn.close()
    for mid, arms in BLOCKED_NINE.items():
        mine = [f for f in found if f.method_id == mid]
        if not mine:
            pytest.skip(f"{mid} is not in this tree's lab database")
        reported = {f.control_id for f in mine if f.verdict == cs.REFUSE}
        assert {a[0] for a in arms} <= reported, f"{mid}: a refusal disappeared from the report"
        assert cs.refusals(mine) or [f for f in mine if f.superseded_by is not None], (
            f"{mid} is no longer read by D17 at all"
        )
