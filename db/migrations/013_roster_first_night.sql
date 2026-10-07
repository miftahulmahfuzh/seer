-- Seer schema v13: the roster the owner chose for the first paper night (owner, 2026-10-07).
--
-- A, F4-FR and F1-FR are retired; RAW-FR, MOM-FR and MVW-FR join RMW-FR and C. Nothing here has
-- ever traded a paper session, so no clock is reset and no started spec moves: 012 was the last
-- schema change before the first night, and this is the last roster change before it.
--
-- WHY THE THREE GO. The screen is owner condition 5 (design section 1) read honestly: can this
-- entry ever satisfy the five conditions at all? Re-run over the lab's 110 recorded dev trials
-- under the bar the owner revised on 2026-10-07 (max DD <= 20%), 27 trials pass all five. None of
-- these three is among them.
--   A        failed its own gate out of sample and again after its one rework: -15.0% and +9.1%
--            against SPY TR's +71.9% and +187.6%, PF 0.92, max DD 33.3% (docs/backtests,
--            2026-10-02). Conditions 2, 3 and 4 all missed, twice measured.
--   F4-FR    max DD 22.2%, outside the revised 20% bar, so condition 4 refuses it permanently.
--   F1-FR    11 closed trades in 22 dev-window years. Condition 1 asks for 100, which at that
--            rate is about two centuries away.
-- A paper slot is a ~15-month commitment at these books' ~80 trades a year (condition 1 binds on
-- trades, not on the 3 months), so a slot that cannot graduate spends that for nothing.
--
-- WHY THE THREE COME. Measured, not assumed. The whole passing set is one bet in several skins --
-- the residual-momentum family runs 0.93-0.99 correlated on monthly dev returns -- and blending
-- it moves the combined MAR from 0.94 to 0.95, a wash. The slots are therefore not bought for
-- ensemble performance, which is not on offer; they are bought as independent forward
-- experiments that could each reach real money.
--   RAW-FR   lab M0007-N20-RAW: RMW-FR's own engine with the volatility brake removed. The one
--            controlled test of the dial that sets the whole risk profile (15.0% a year at a
--            19.6% fall against RMW's 11.7% at 14.3%), and the entry the revised 20% bar newly
--            admits -- under the old 15% bar it was ineligible.
--   MOM-FR   lab M0002-REL-85: F4's total-return-momentum bet (0.99 correlated with F4's own
--            variant) at max DD 18.4% instead of 22.2%, so the same bet can actually graduate.
--   MVW-FR   lab M0008-N30-C07: the only passing variant that changes the sizing rather than the
--            ranking, and at 0.81 the least correlated with RMW-FR of any passer. Its max DD is
--            20.0%, exactly the bar, with no margin -- the known risk of this admission.
--
-- Backtested in whole shares under monthly-hold; these trade fractional shares under
-- monthly-hold-frac, as 010 did for F4 and F1. Each row is what `promote --method <M> --candidate
-- <variant> --fractional --lab-override-reason "..."` writes on the live database; this file
-- writes it everywhere else, byte for byte paper/roster.py's SEED_ROWS (the migration-equality
-- test, tests/test_paper_roster.py). paper_start, the frozen spec and the paper clock are written
-- by the first night, as for every new entry.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('RAW-FR', 'RAW · Unbraked momentum', 'Top 20 by rise beyond the market, no brake, monthly, fractional shares', 'zap', false, false, 11, 'book', 'monthly-hold-frac', 'RESIDMOM', NULL, 'Lab M0007 dev window only (1996-01-03..2015-10-16), in whole shares: beats SPY TR (+1,502.2% vs +351.4%), max DD 19.6%, PF 2.16 and 1,596 trades all pass. It does NOT pass the luck test: 0.914 at the N=85 it was scored at, 0.899 re-scored at today''s N=110, just under the 0.90 bar. Never had a test-window look. On paper as the controlled comparison against RMW-FR: the same book without the brake', true, 'M0007'),
  ('MOM-FR', 'MOM · Regime momentum', 'Top 20 by last year''s rise, holds less when jumpy for itself, monthly, fractional shares', 'trending-up', false, false, 12, 'book', 'monthly-hold-frac', 'REGIME', NULL, 'Lab M0002 dev window only (1996-01-03..2015-10-16), in whole shares: beats SPY TR (+940.1% vs +351.4%), max DD 18.4%, PF 2.33 and 1,148 trades all pass; failed only the luck test (0.854 at the N=80 it was scored at, 0.828 at today''s N=110). Replaces F4-FR: the same total-return-momentum bet, inside the 20% drawdown bar that F4''s 22.2% cannot meet. On paper to test it forward', true, 'M0002'),
  ('MVW-FR', 'MVW · Steady weights', 'Top 30 by last year''s rise, weighted to swing least together, monthly, fractional shares', 'scale', false, false, 13, 'book', 'monthly-hold-frac', 'MINVAR', NULL, 'Lab M0008 dev window only (1996-01-03..2015-10-16), in whole shares: beats SPY TR (+726.7% vs +351.4%), max DD 20.0%, PF 2.14 and 1,223 trades all pass; failed only the luck test (0.817 at the N=74 it was scored at, 0.780 at today''s N=110). Replaces F1-FR, which cannot reach 100 closed trades. Its drawdown sits exactly on the 20% bar, with no margin. On paper to test it forward', true, 'M0008')
ON CONFLICT (id) DO NOTHING;

-- Retiring keeps every row they wrote and the next paper night stamps their paper_end. None of
-- the three has a paper_start, so there is nothing to stamp and nothing to lose.
UPDATE strategies SET status = 'retired'
WHERE id IN ('A', 'F4-MOM12-N20-TREND-FR', 'F1-SPY-SMA200-M-FR') AND status = 'active';
