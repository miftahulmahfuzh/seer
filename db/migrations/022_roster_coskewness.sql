-- Seer schema v22: COSK-FR-GT joins the roster and RMW-FR-GT retires (owner, 2026-10-17).
--
-- The owner's request: put lab variant M0179-N20 on the paper roster and retire RMW-FR-GT to make
-- room. He means to move the money he holds in RAW's twenty real positions into whatever this
-- entry picks, so its live picks are the point of the admission, not a side effect.
--
-- WHAT IT IS. Lab M0179 (Harvey & Siddique 2000, coskewness): among the members passing F4's
-- $5 / $20M screen, each one's standardized coskewness with SPY over 156 non-overlapping weekly
-- returns (three years); hold the 20 most negative -- the stocks that fall hardest in the weeks the
-- market swings hardest -- at 1/20 each; re-rank on the last close of March, June, September and
-- December, keeping a holding while its rank fraction stays under 40%; slots with no stock sit in
-- SPY; no market switch. Rules monthly-hold-frac-gotrade: fractional shares at Gotrade's measured
-- fees. The params are read from the frozen method file's M0179-N20 Candidate, which is not edited.
--
-- THIS IS AN OWNER OVERRIDE AND NOT A LAB PASS, and the row says so in its gate note. M0179 reads
-- dev-eligible only through its 40-name switched rung (N40-SW). The variant admitted here FAILED the
-- dev screen: funded on the owner's plan it returns +359.6% against a deposit-matched SPY TR's
-- +257.2% (10.1% a year against 7.2%), PF 2.20, 506 trades -- but max DD 51.7%, outside the
-- screen's 50% and twice the owner's 25% real-money bar, and a recorded DSR of 0.500 at its
-- recorded N=116. The hard gate refuses the method on its walk-forward folds: 2 of 4 won, with the
-- opposite (most positive) picks preferred before every fold. Its recorded verdict is "not
-- promoted". It has never had a test-window look and none is spent here. The roster's admission
-- rule has always been the owner's (paper/roster.py's module docstring): a lab pass is sufficient
-- for paper, never necessary. paper/roster.py's LAB_PROVENANCE carries the same facts.
--
-- A FEED BUG FIXED IN THE SAME CHANGE, NOT HERE. The signal samples SPY's last 781 sessions, but
-- the method's allocator declares only its screen's 253-bar lookback, and the paper night loaded
-- 640 calendar days (~440 sessions). Every member would have gone unscored and every slot would
-- have sat in SPY. paper.store.MARKET_WINDOW_DAYS is now 1200 (~825 sessions) and
-- paper.roster.HISTORY_FLOOR_BARS states the true 781-session need, so the night's own window
-- guard refuses to run this entry on a window that cannot feed it. Neither is schema.
--
-- WHY A NEW ID. Nothing is edited: COSK is a new object with its own frozen spec and its own clock.
-- RMW-FR-GT is RETIRED, not deleted: it keeps every row it ever wrote, its digest does not move
-- (status, sort and paper_end are outside the frozen spec), and it stays reachable on the
-- leaderboard's retired list.
--
-- WHY THE MIGRATION AND NOT `promote`. `promote` could place this row (COSKEW has one resolver
-- name), but it writes the live database and lab/lab.sqlite in one step. This change writes the
-- row the way 021 did -- the migration is the only writer everywhere -- and any lab promotion note
-- is recorded separately on the lab's side.
--
-- NOT TOUCHED. The section 1 real-money bar (18 months of paper, beat SPY, PF >= 1.3, max DD <=
-- 25%, a 10-year backtest), which changes only through a dated owner revision; this entry fails
-- its drawdown on the dev window and paper is where that is watched, not waived. backtest/
-- registry.py. Any lab row. RAW35-FR-GT, where the owner's real money sits today.
--
-- The row below is byte for byte paper/roster.py's SEED_ROWS (the migration-equality test,
-- tests/test_paper_roster.py::test_the_migration_rows_equal_the_seed_rows). paper_start, the
-- frozen spec and the paper clock are written by the entry's first night, as for every new entry.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('COSK-FR-GT', 'COSK · Crash-prone picks', '20 stocks that fall hardest in the market''s wildest weeks, re-picked each quarter, fractional shares, real Gotrade fees', 'cloud-lightning', false, false, 3, 'book', 'monthly-hold-frac-gotrade', 'COSKEW', NULL, 'Owner override, 2026-10-17, admitted for paper after his calculate-assets run; NOT a lab pass. Lab M0179 dev window only (1996-01-03..2015-10-16), already in fractional shares at Gotrade''s measured fees on the owner''s funding plan -- the rule set this entry runs: +359.6% against a deposit-matched SPY TR''s +257.2% (10.1% a year against 7.2%), PF 2.20, 506 trades, but max DD 51.7% -- outside the lab screen''s 50% and twice the owner''s 25% real-money bar -- and a recorded DSR of 0.500 at its recorded N=116, so this variant FAILED the dev screen. M0179 reads dev-eligible only through its 40-name switched rung, and the hard gate refuses the method on its walk-forward folds (2 of 4). Never had a test-window look. It replaces RMW-FR-GT. On paper because the owner means to move the money he holds in RAW''s book into its picks', true, 'M0179')
ON CONFLICT (id) DO NOTHING;

-- Retiring stamps paper_end with the last session the entry actually traded, which is
-- paper_state.last_session -- exactly what paper/store.py's `retire` writes and what 021 wrote for
-- RAW-FR-GT. No equity_snapshots, orders, book_positions, book_targets, book_fills, book_trades or
-- paper_state row is touched: RMW-FR-GT keeps its whole track record.
UPDATE strategies AS s SET
    status = 'retired',
    paper_end = (SELECT ps.last_session FROM paper_state ps WHERE ps.strategy_id = s.id)
WHERE s.id = 'RMW-FR-GT' AND s.status = 'active';

-- Sort is display order: the six that trade first, then the fifteen retired, in the order they
-- were retired. COSK-FR-GT takes the slot RMW-FR-GT held. `sort` is not in the frozen spec, so no
-- digest moves.
UPDATE strategies SET sort = 21 WHERE id = 'RMW-FR-GT';
