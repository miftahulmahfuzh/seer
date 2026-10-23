-- Seer schema v23: the roster gains an always-invested control (owner, 2026-10-23).
--
-- The owner's instruction, after reading the calculate-assets pages for this batch's four methods:
-- confirm M0287-FULL is the gate-off arm, then "replace one of the seer's roster with it. keep C,
-- COSK, RAW35". It is the gate-off arm -- M0287 registers it as "none, the gate switched off ...
-- the no-opinion endpoint", 98.6% invested, horizons=None -- and this migration admits it and
-- retires MVW-FR-GT to make room.
--
-- WHY MVW AND NOT MOM. The owner named three entries to keep and left the fourth choice open. MVW
-- weights momentum picks for minimum variance instead of equally; that is the roster idea the lab
-- has the most evidence against. M0286, measured on the owner's OWN window three days before this
-- migration, puts the market's own shape 3.3 points a year ahead of an alternative weighting of
-- identical names, and an earlier 8-point equal-weight lead decomposed to 3.6 of gate, 3.8 of fees
-- and 0.9 of actual weighting. MOM is also kept because MOM beside RAW35 is the braked/unbraked
-- pair, which is the comparison that would be lost. MVW-FR-GT is RETIRED, not deleted: it keeps
-- every row it ever wrote and stays on the leaderboard.
--
-- WHAT THIS ENTRY IS. Fifty index members over $20m a day and above $5, equal slices, rebalanced
-- in full every month, never out of the market -- no SPY 200-day switch, no volatility brake, no
-- weighting opinion. It is a CONTROL and the gate_note says so in its first sentence. C has been
-- on this roster permanently since 017 as the daily-trading control, because measuring how bad
-- daily trading would have been IS the finding. This is the complement: how bad, or good, never
-- stepping aside would have been. Every other book on the board defends itself somehow, and
-- nothing here has ever measured the absence of that forward.
--
-- WHAT IT FAILED. On the lab's dev window it failed ALL FOUR conditions and M0287 is REJECTED:
-- funded on the owner's own plan it returns +250.3% against a deposit-matched SPY TR's +257.2%
-- (6.9% a year against 7.2% -- it LOSES), max DD 59.5% against the screen's 50% and the owner's
-- 25% real-money bar, PF 1.25 against 1.30, and a recorded DSR of 0.414 at its recorded N=184 on
-- 1,338 trades. It has never had a test-window look and never will be put forward for one.
--
-- WHAT PUT IT HERE ANYWAY. The other window. Over 2018-04-02..2026-10-08, on the owner's real
-- deposits at Gotrade's real fees, it ended at Rp 1,558,671,049 -- +24.6% a year against SPY's
-- +20.4% -- the only arm of this batch's four methods to beat the market, with a 33.3% fall. Those
-- two readings are the entry: a book with no defence wins a decade with no long bear market in it
-- and loses the one that has two. The dev verdict was earned in 1996-2002 and in 2008, and the
-- owner's money has never lived through a fall of that kind. Watching it forward beside C is how
-- the roster finds out which kind of decade it is in, and it costs no test-window look to do.
--
-- THE CHASSIS IS PART OF THE BOOK, AND IT IS WHY sim.rules GREW A PRESET. M0287 measured on
-- monthly-hold-frac-gotrade-tband00: the target basis with resize_band = 0, so every non-zero gap
-- is beyond the band and every holding is traded back to its slot each month. M0127 registered
-- that tape and M0266, M0270, M0271 and M0287 have all measured on it, because a book that
-- rebalances completely is the only chassis on which an exposure experiment means what it says.
-- It lived in M0127's method file, and paper/roster.py's `rules_for` resolves a rules_id against
-- sim.rules.PRESETS alone, so no roster entry could name it. Admitting this book on the roster's
-- usual preset instead would have been a DIFFERENT book wearing this one's +24.6%, so the preset
-- was added to sim.rules (field-for-field equal to M0127's T00 -- asserted in
-- tests/test_sim_rules_fixed_tape.py -- so no recorded trial's digest moves) and M0127 was left
-- exactly as committed, because a method file is a pre-registration and is never edited. The web
-- mirrors learned it in the same commit (cadence.ts TARGET_BAND_RULES, sean/reminders.ts
-- RESIZING_RULES; tests/test_sean_mirrors.py derives both from PRESETS).
--
-- WHY A MIGRATION AND NOT `promote`. The same reason as 021 and 022: commands/promote.py's
-- object_name_of inverts RESOLVER by object identity, and this is an owner override of a REJECTED
-- method, which `promote` would refuse outright and should. lab/lab.sqlite is untouched by this
-- change -- no record_promotion note, no status move, no trial, and the lab's N and its four spent
-- test-window looks do not move. The roster states the provenance on its own side, as it always
-- has (paper/roster.py LAB_PROVENANCE).
--
-- NOT TOUCHED. The section 1 real-money bar, which changes only through a dated owner revision --
-- and nothing here goes near real money: this is a paper control. backtest/registry.py. Any lab
-- row. MOM-FR-GT, COSK-FR-GT and RAW35-FR-GT, the three the owner named.
--
-- The row below is byte for byte paper/roster.py's SEED_ROWS (the migration-equality test,
-- tests/test_paper_roster.py::test_the_migration_rows_equal_the_seed_rows). paper_start, the
-- frozen spec and the paper clock are written by the entry's first night, as for every new entry.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('FULL50-FR-GT', 'FULL50 · Never steps aside', 'The 50 most-traded members at equal weight, fully rebalanced monthly, never in cash, fractional shares, real Gotrade fees', 'anchor', false, false, 6, 'book', 'monthly-hold-frac-gotrade-tband00', 'ALLINVESTED', NULL, 'A CONTROL, not a candidate: the always-invested complement of C, here to measure what never stepping aside costs or pays. Owner override, 2026-10-23, after his calculate-assets run; NOT a lab pass, and the method it comes from is REJECTED. Lab M0287 dev window only (1996-01-03..2015-10-16), already in fractional shares at Gotrade''s measured fees on the owner''s funding plan -- the rule set this entry runs: it FAILED every condition, losing to a deposit-matched SPY TR (+250.3% against +257.2%, 6.9% a year against 7.2%), max DD 59.5% -- outside the lab screen''s 50% and well past the owner''s 25% real-money bar -- PF 1.25 against the 1.30 bar, and a recorded DSR of 0.414 at its recorded N=184, on 1,338 trades. Never had a test-window look. What put it here is the other window: over 2018-04-02..2026-10-08 on the owner''s real deposits it ended at Rp 1,558,671,049, +24.6% a year against SPY''s +20.4%, the only arm of the four methods explored that beat the market -- and it fell 33.3% doing it. A book with no defence wins a decade without a long bear market and loses the one with two in it. It replaces MVW-FR-GT', true, 'M0287')
ON CONFLICT (id) DO NOTHING;

-- Retiring stamps paper_end with the last session the entry actually traded, which is
-- paper_state.last_session -- exactly what paper/store.py's `retire` writes and what 021 and 022
-- wrote. No equity_snapshots, orders, book_positions, book_targets, book_fills, book_trades or
-- paper_state row is touched: MVW-FR-GT keeps its whole track record.
UPDATE strategies AS s SET
    status = 'retired',
    paper_end = (SELECT ps.last_session FROM paper_state ps WHERE ps.strategy_id = s.id)
WHERE s.id = 'MVW-FR-GT' AND s.status = 'active';

-- Sort is display order: the six that trade first, then the sixteen retired, in the order they
-- were retired. FULL50-FR-GT takes the slot MVW-FR-GT held. `sort` is not in the frozen spec, so
-- no digest moves.
UPDATE strategies SET sort = 22 WHERE id = 'MVW-FR-GT';
