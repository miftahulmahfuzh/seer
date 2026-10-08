-- Seer schema v18: six gate notes said "today's N", naming a count that has since moved.
--
-- The notes for RAW, MOM and MVW (both the flat-fee originals and their Gotrade successors) each
-- carried a luck score re-scored at "today's N = 110" -- the live count on the night each entry
-- was admitted. N is not a constant: the policy moved from counting trial rows to counting
-- distinct methods on 2026-10-08, and the count moves again whenever a method is registered. So
-- those clauses stated a live fact inside a frozen string, and two had since inverted -- RAW
-- re-scores to 0.961 today and MOM to 0.921, both clear of the bar, while the note still said
-- they failed the luck test.
--
-- The fix states each variant's RECORDED score at its OWN recorded N. `trials` is append-only, so
-- that pair can never go stale; the live verdict is left to the method page, which reads `dsrNow`
-- against the live gate (web/data/lab.json). This is the phrasing the lab's own promotion record
-- already uses -- "recorded DSR 0.914 at its recorded N = 85" -- so this brings the roster's copy
-- INTO agreement with the permanent record rather than away from it.
--
-- NOT touched: RMW's note, which reads "0.916 at N=110". For M0022-W-TV16, 110 IS the recorded N,
-- so that one is correct history. The coincidence of the number is exactly why each note was
-- checked against trials.n_trials_at_run instead of pattern-matched on "110".
--
-- Display only: `gate_note` is not in roster.spec, so no frozen spec digest moves and no paper
-- clock is touched (the same reason 017 could move is_champion). Idempotent: a plain UPDATE of a
-- literal, safe to replay.
--
-- The text below is generated from paper/roster.py's SEED_ROWS, which
-- tests/test_paper_roster.py::test_the_migration_rows_equal_the_seed_rows compares this table
-- against row for row -- so the two cannot drift.

UPDATE strategies SET gate_note = 'Lab M0007 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed 0.1% a side: beats SPY TR (+1,502.2% vs +351.4%), max DD 19.6%, PF 2.16 and 1,596 trades all pass, on a recorded DSR of 0.914 at its recorded N=85; its method was rejected under the older 15% drawdown bar. Never had a test-window look. Re-measured at Gotrade''s real fees (449fa34, report only) it returns +1,126% against SPY''s +350% at the same fees. Successor of RAW-FR, which paid the assumed rate. On paper as the controlled comparison against RMW-FR-GT: the same book without the brake'
  WHERE id = 'RAW-FR-GT';

UPDATE strategies SET gate_note = 'Lab M0002 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed 0.1% a side: beats SPY TR (+940.1% vs +351.4%), max DD 18.4%, PF 2.33 and 1,148 trades all pass; failed only the luck test, on a recorded DSR of 0.854 at its recorded N=80. Re-measured at Gotrade''s real fees (449fa34, report only) it returns +763% against SPY''s +350% at the same fees. Successor of MOM-FR, which paid the assumed rate. On paper to test it forward'
  WHERE id = 'MOM-FR-GT';

UPDATE strategies SET gate_note = 'Lab M0008 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed 0.1% a side: beats SPY TR (+726.7% vs +351.4%), max DD 20.0%, PF 2.14 and 1,223 trades all pass; failed only the luck test, on a recorded DSR of 0.817 at its recorded N=74. Re-measured at Gotrade''s real fees (449fa34, report only) it returns +536% against SPY''s +350% at the same fees. Successor of MVW-FR, which paid the assumed rate. Its drawdown sits exactly on the 20% bar, with no margin. On paper to test it forward'
  WHERE id = 'MVW-FR-GT';

UPDATE strategies SET gate_note = 'Lab M0007 dev window only (1996-01-03..2015-10-16), in whole shares: beats SPY TR (+1,502.2% vs +351.4%), max DD 19.6%, PF 2.16 and 1,596 trades all pass, on a recorded DSR of 0.914 at its recorded N=85; its method was rejected under the older 15% drawdown bar. Never had a test-window look. On paper as the controlled comparison against RMW-FR: the same book without the brake'
  WHERE id = 'RAW-FR';

UPDATE strategies SET gate_note = 'Lab M0002 dev window only (1996-01-03..2015-10-16), in whole shares: beats SPY TR (+940.1% vs +351.4%), max DD 18.4%, PF 2.33 and 1,148 trades all pass; failed only the luck test, on a recorded DSR of 0.854 at its recorded N=80. Replaces F4-FR: the same total-return-momentum bet, inside the 20% drawdown bar that F4''s 22.2% cannot meet. On paper to test it forward'
  WHERE id = 'MOM-FR';

UPDATE strategies SET gate_note = 'Lab M0008 dev window only (1996-01-03..2015-10-16), in whole shares: beats SPY TR (+726.7% vs +351.4%), max DD 20.0%, PF 2.14 and 1,223 trades all pass; failed only the luck test, on a recorded DSR of 0.817 at its recorded N=74. Replaces F1-FR, which cannot reach 100 closed trades. Its drawdown sits exactly on the 20% bar, with no margin. On paper to test it forward'
  WHERE id = 'MVW-FR';

