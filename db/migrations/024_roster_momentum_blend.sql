-- Seer schema v24: the roster swaps MOM for a momentum blend (owner, 2026-10-31).
--
-- The owner's instruction, after the calculate-assets run of M0294 and a ranking of four roster
-- candidates on the same 2018-04-01 start, his real deposits and Gotrade's real fees: put
-- M0294-M70-MOM30 on the roster and "kick MOM out". The ranking, by money-weighted return at
-- real rupiah: COSK +27.6% a year, M70-MOM30 +25.1%, FULL50 +25.1%, MOM +10.4% against SPY's
-- +20.5%. MOM was last by a wide margin and the only one of the four to lose to SPY.
-- MOM-FR-GT is RETIRED, not deleted: it keeps every row it ever wrote and stays on the board.
--
-- WHAT THIS ENTRY IS. 70% of the book in the thirty strongest twelve-minus-one-month momentum
-- names, 30% in SPY at all times, monthly, no market switch, no cash, on the roster's usual
-- monthly-hold-frac-gotrade preset -- so no new preset and no web lever. It is M0294's M70-MOM30
-- arm, the allocator the generic core-and-satellite BLEND with the shares in its params.
--
-- WHAT IT FAILED, AND WHY IT IS HERE ANYWAY. M0294 is REJECTED. On the dev window this arm fails
-- two conditions: max DD 57.1% against the screen's 50%, and a recorded DSR of 0.548 at N=255
-- against 0.90. It beats SPY TR there (+295.1% against +257.2%, PF 1.54, 2,048 trades) and has
-- never had a test-window look. On 2018-04-02..2026-10-06 it ended at Rp 1,595,573,111, +25.1% a
-- year against SPY's +20.5%, with a 34.6% fall. The fall and a published momentum edge expected
-- to fade are the risks of this admission. Paper is how it earns, or loses, the right to be
-- taken seriously.
--
-- WHY A MIGRATION AND NOT `promote`. As for 021 to 023: this is an owner override of a REJECTED
-- method, which `promote` refuses and should. lab/lab.sqlite is untouched -- no status move, no
-- trial, no test-window look.
--
-- NOT TOUCHED. The section 1 real-money bar, backtest/registry.py, any lab row, and C-GT,
-- COSK-FR-GT, RAW35-FR-GT and FULL50-FR-GT.
--
-- The row below is byte for byte paper/roster.py's SEED_ROWS (the migration-equality test,
-- tests/test_paper_roster.py::test_the_migration_rows_equal_the_seed_rows). paper_start, the
-- frozen spec and the paper clock are written by the entry's first night, as for every new entry.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('MOM70-FR-GT', 'MOM70 · Momentum beside SPY', '70% in the 30 strongest names by last year''s rise, 30% in SPY, monthly, fractional shares, real Gotrade fees', 'trending-up', false, false, 5, 'book', 'monthly-hold-frac-gotrade', 'MOMBLEND70', NULL, 'Owner override, 2026-10-31, after his calculate-assets run; NOT a lab pass, and the method it comes from is REJECTED. Lab M0294 dev window only (1996-01-03..2015-10-16), already in fractional shares at Gotrade''s measured fees on the owner''s funding plan -- the rule set this entry runs: it beats SPY TR (+295.1% against +257.2%) with PF 1.54 on 2,048 trades, but its max DD is 57.1% -- outside the lab screen''s 50% and well past the owner''s 25% real-money bar -- and its recorded DSR is 0.548 at its recorded N=255 against the 0.90 bar. Never had a test-window look. What put it here is the other window: over 2018-04-02..2026-10-06 on the owner''s real deposits it ended at Rp 1,595,573,111, +25.1% a year against SPY''s +20.5%, and it fell 34.6% doing it. Momentum is a published edge and is expected to fade. It replaces MOM-FR-GT', true, 'M0294')
ON CONFLICT (id) DO NOTHING;

-- Retiring stamps paper_end with the last session the entry actually traded, which is
-- paper_state.last_session -- exactly what paper/store.py's `retire` writes and what 021 to 023
-- wrote. No equity_snapshots, orders, book_positions, book_targets, book_fills, book_trades or
-- paper_state row is touched: MOM-FR-GT keeps its whole track record.
UPDATE strategies AS s SET
    status = 'retired',
    paper_end = (SELECT ps.last_session FROM paper_state ps WHERE ps.strategy_id = s.id)
WHERE s.id = 'MOM-FR-GT' AND s.status = 'active';

-- Sort is display order: the six that trade first, then the retired, in the order they were
-- retired. MOM70-FR-GT takes the slot MOM-FR-GT held. `sort` is not in the frozen spec, so no
-- digest moves.
UPDATE strategies SET sort = 23 WHERE id = 'MOM-FR-GT';
