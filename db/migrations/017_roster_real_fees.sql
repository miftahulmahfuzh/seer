-- Seer schema v17: the roster pays Gotrade's real fees (owner, 2026-10-08).
--
-- Every entry on the roster assumed a flat 0.1% a side. Sean measured what Gotrade actually
-- charges against 30 of the owner's own receipts and fitted sim/costs.py to them; it reproduces
-- both sides of his 2026-10-07 activity to the cent ($27.90 buy -> $0.13 charged, receipt $28.03
-- paid; $72.51 sell -> $0.24, receipt $72.27 received). Measured through costs.fee_parts, a round
-- trip costs:
--     $10 -> 2.500%   $28 -> 1.036%   $50 -> 0.620%   $560 -> 0.534%   $5,000 -> 0.493%
-- against the 0.200% assumed: 12.5x, 5.2x, 3.1x, 2.7x, 2.5x. The asymptote is about 2.5x the
-- assumed rate; everything above it is the $0.10 per-order floor, which binds below about $50 an
-- order. The owner's own 20 real buys cost $2.60 to deploy $558 -- 0.47% of the book gone before a
-- single round trip.
--
-- WHY SIX NEW IDS AND NOT SIX EDITS. `cost_model` sits in sim.rules.LEVERS_SINCE_PINS at its no-op
-- "flat", so moving a STARTED entry to "gotrade" changes its frozen spec digest and
-- store.check_digest refuses its next night with a SpecMismatch. docs/runbooks/paper-trading.md
-- states the rule: to change anything about a strategy, add a NEW roster entry with a NEW id; its
-- paper clock starts on its own first night; never edit an entry that has a paper_start and never
-- reset a clock by deleting rows. 010, 011 and 013 are the precedents. The predecessors are
-- RETIRED here, not deleted: a retired entry keeps every row it ever wrote.
--
-- WHY IT IS FREE. Measured against production before this was written: paper_state.last_session is
-- 2026-10-06, pending_session is 2026-10-07, and NO session has ever been stepped --
-- equity_snapshots holds only the starting rows at 560.5067 USD. A fresh clock therefore throws
-- away no paper history at all. Paper has been paused since 2026-10-08 precisely to keep that
-- true, and it stays paused: nightly.yml's PAPER_PAUSED is still 'true', which skips Veto, Paper,
-- Paper check and Explain while Migrate and Nightly (bars) always run. So THIS MIGRATION APPLIES
-- on the next nightly, and nothing else happens -- no paper_start is written and no session is
-- stepped until the owner flips the switch himself.
--
-- WHAT THE SIX ARE.
--   SPY-GT      the yardstick pays what the methods pay. SPY bought at a flat 0.1% a side, so
--               "beats SPY TR" was comparing a cheap benchmark against expensive strategies. A
--               benchmark row carries no rules_id, so its cost model is stated in
--               paper/roster.py's BENCHMARK_COST_MODEL and recorded in its spec.
--   C-GT        the DAILY-TRADING CONTROL, and it stays on this roster permanently (owner's
--               standing instruction, 2026-10-08): "we must always include a daily trading method
--               like C in the roster because I want to see how bad it got if I had used daily
--               trading on Gotrade like my initial plan". Daily trading was his original plan; C
--               is the measured counterfactual, and being expensive is the finding it exists to
--               produce. It is never retired on cost grounds. It answers his question only if it
--               runs on the same starting capital, the same monthly deposits and the same fee
--               schedule as the monthly books, and it carries all three.
--   RMW-FR-GT   lab M0022-W-TV16, RAW-FR-GT lab M0007-N20-RAW, MOM-FR-GT lab M0002-REL-85,
--   RAW-FR-GT   MVW-FR-GT lab M0008-N30-C07 -- the same four methods and the same four recorded
--   MOM-FR-GT   variants that are on the roster today, under the Gotrade fee presets
--   MVW-FR-GT   (monthly-hold-frac-gotrade and monthly-rank-weekly-resize-frac-gotrade).
--
-- WHAT DOES NOT CHANGE. The books still hold 20 names. The fee argument for holding fewer is a
-- two-month transient under the owner's funding plan: measured at 17,841 IDR/USD, by month 3 a
-- 20-name book pays 0.614% and an 11-name book 0.612%. How many names to hold is a question about
-- returns, and if it is ever answered differently the answer lands as a FURTHER entry under the
-- same rule, never as an edit to a running one.
--
-- THE BACKTEST NUMBERS IN THE gate_note COLUMNS, and a caveat that must travel with them. The
-- roster re-measured at real fees (449fa34, report only -- the lab's own N is unchanged) reads
-- RAW +1502% -> +1126%, MOM +940% -> +763%, MVW +727% -> +536%, RMW +789% -> +543%, with SPY at
-- the same fees +350%. All four still beat SPY, so no verdict is overturned. Those averages run
-- over a growth path from a 20M IDR lump to +1126%, so the floor binds hard in the early years and
-- is irrelevant later: the owner sits at the EXPENSIVE end of that path today and these figures
-- UNDERSTATE his near-term drag. The backtest average and today's rate are two different numbers.
--
-- Each row below is byte for byte paper/roster.py's SEED_ROWS (the migration-equality test,
-- tests/test_paper_roster.py). paper_start, the frozen spec and the paper clock are written by the
-- first unpaused night, as for every new entry.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('SPY-GT', 'SPY', 'S&P 500, buy and hold, real Gotrade fees', 'landmark', true, true, 1, 'benchmark', NULL, 'buy_and_hold', NULL, 'Benchmark, not a strategy: it has no backtest gate and is never a Seer pick. It replaces SPY, which bought at a flat 0.1% a side while every method now pays Gotrade''s measured schedule -- a yardstick cheaper than the thing it measures. Over the lab''s dev window at the same real fees SPY returns +350%', true, NULL),
  ('C-GT', 'C · News veto', 'A''s picks, LLM can veto on news, daily, real Gotrade fees', 'gavel', false, false, 2, 'bracket', 'design-v0-gotrade', 'STRATEGY_C', NULL, 'Backtest gate: not applicable (LLM strategy, design section 1 item 5). On the roster PERMANENTLY as the daily-trading control (owner, 2026-10-08): it measures how bad daily trading on Gotrade would have been, which was the owner''s original plan. Being expensive is the finding it exists to produce, so it is never retired on cost grounds. It answers that question only if it runs on the same starting capital, the same monthly contributions and the same fee schedule as the monthly books, and it carries all three', false, NULL),
  ('RMW-FR-GT', 'RMW · Braked momentum', 'Top 20 by rise beyond the market, picked monthly; holds less when jumpy, checked weekly; fractional shares, real Gotrade fees', 'activity', false, false, 3, 'book', 'monthly-rank-weekly-resize-frac-gotrade', 'WEEKLYBRAKE', NULL, 'Lab M0022 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed 0.1% a side: beats SPY TR (+789.2% vs +351.4%), max DD 14.3%, PF 2.06 and 1,589 trades all pass; failed only DSR >= 0.95 (0.916 at N=110). Re-measured at Gotrade''s real fees (449fa34, report only -- the lab''s own N is unchanged) it returns +543% against SPY''s +350% at the same fees, so no verdict moves. Successor of RMW-FR, which paid the assumed rate; this entry pays Gotrade''s measured schedule from its first night. On paper to test it forward', true, 'M0022'),
  ('RAW-FR-GT', 'RAW · Unbraked momentum', 'Top 20 by rise beyond the market, no brake, monthly, fractional shares, real Gotrade fees', 'zap', false, false, 4, 'book', 'monthly-hold-frac-gotrade', 'RESIDMOM', NULL, 'Lab M0007 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed 0.1% a side: beats SPY TR (+1,502.2% vs +351.4%), max DD 19.6%, PF 2.16 and 1,596 trades all pass. It does NOT pass the luck test: 0.914 at the N=85 it was scored at, 0.899 re-scored at today''s N=110, just under the 0.90 bar. Never had a test-window look. Re-measured at Gotrade''s real fees (449fa34, report only) it returns +1,126% against SPY''s +350% at the same fees. Successor of RAW-FR, which paid the assumed rate. On paper as the controlled comparison against RMW-FR-GT: the same book without the brake', true, 'M0007'),
  ('MOM-FR-GT', 'MOM · Regime momentum', 'Top 20 by last year''s rise, holds less when jumpy for itself, monthly, fractional shares, real Gotrade fees', 'trending-up', false, false, 5, 'book', 'monthly-hold-frac-gotrade', 'REGIME', NULL, 'Lab M0002 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed 0.1% a side: beats SPY TR (+940.1% vs +351.4%), max DD 18.4%, PF 2.33 and 1,148 trades all pass; failed only the luck test (0.854 at the N=80 it was scored at, 0.828 at today''s N=110). Re-measured at Gotrade''s real fees (449fa34, report only) it returns +763% against SPY''s +350% at the same fees. Successor of MOM-FR, which paid the assumed rate. On paper to test it forward', true, 'M0002'),
  ('MVW-FR-GT', 'MVW · Steady weights', 'Top 30 by last year''s rise, weighted to swing least together, monthly, fractional shares, real Gotrade fees', 'scale', false, false, 6, 'book', 'monthly-hold-frac-gotrade', 'MINVAR', NULL, 'Lab M0008 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed 0.1% a side: beats SPY TR (+726.7% vs +351.4%), max DD 20.0%, PF 2.14 and 1,223 trades all pass; failed only the luck test (0.817 at the N=74 it was scored at, 0.780 at today''s N=110). Re-measured at Gotrade''s real fees (449fa34, report only) it returns +536% against SPY''s +350% at the same fees. Successor of MVW-FR, which paid the assumed rate. Its drawdown sits exactly on the 20% bar, with no margin. On paper to test it forward', true, 'M0008')
ON CONFLICT (id) DO NOTHING;

-- Retiring keeps every row they wrote and the next unpaused night stamps their paper_end. None of
-- the six has a paper_start -- zero sessions were ever stepped -- so there is nothing to stamp and
-- nothing to lose. Their 2026-10-07 pending decisions (80 book_targets rows and 4 orders) stay on
-- the record as what was decided and never acted on; they are not deleted.
UPDATE strategies SET status = 'retired'
WHERE id IN ('SPY', 'C', 'RMW-FR', 'RAW-FR', 'MOM-FR', 'MVW-FR') AND status = 'active';

-- The champion and the benchmark are SPY-GT now. Both are display fields and neither is in the
-- frozen spec, so moving them does not touch the retired SPY's digest.
UPDATE strategies SET is_champion = false, is_benchmark = false WHERE id = 'SPY';

-- Sort is display order: the six that trade come first, then the thirteen that are retired, in the
-- order they were added. Not in the spec either, so no digest moves.
UPDATE strategies AS s SET sort = v.sort
FROM (VALUES
  ('SPY', 7), ('A', 8), ('F4-MOM12-N20-TREND', 9), ('F1-SPY-SMA200-M', 10), ('C', 11),
  ('FND', 12), ('F4-MOM12-N20-TREND-FR', 13), ('F1-SPY-SMA200-M-FR', 14), ('RM-FR', 15),
  ('RMW-FR', 16), ('RAW-FR', 17), ('MOM-FR', 18), ('MVW-FR', 19)
) AS v(id, sort)
WHERE s.id = v.id;
