-- Seer schema v10: F4 and F1 trade fractional shares, and RM replaces FND (owner, 2026-10-07).
--
-- Gotrade takes fractional LIMIT buys and sells (only its take-profit/stop-loss order needs whole
-- shares, and the book methods never use one). In whole shares a 10,000,000 IDR book could not
-- hold most of F4's 20 targets (about $55 each) and F1 could hold one SPY share of its $1,116, so
-- the paper record would not have been the method the owner trades.
--
-- A changed rule set is a NEW roster id (paper runbook, "The roster"): F4 and F1 come back under
-- monthly-hold-frac as F4-MOM12-N20-TREND-FR and F1-SPY-SMA200-M-FR, the same registry candidates.
-- FND is not carried over: the owner replaced it with RM, lab M0011's braked residual momentum
-- (RAW20-TV14-N21), the only lab book that passes every owner rule and fails only the luck test.
-- RM-FR is the row `promote --method M0011 --candidate M0011-RAW20-TV14-N21 --fractional` writes
-- on the live database (promoted_from M0011); this file writes it everywhere else, as 007 does
-- for FND. The whole-share F4, F1 and FND are retired; retiring keeps every row they wrote and the
-- next paper night stamps their paper_end. paper_start, the frozen spec and the paper clock of the
-- new rows are written by that night, as for every new entry. Rows below are byte for byte
-- paper/roster.py's SEED_ROWS (the migration-equality test).
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('F4-MOM12-N20-TREND-FR', 'F4 · Momentum', 'Top 20 by last year''s rise, monthly, fractional shares',
   'trending-up', false, false, 7, 'book', 'monthly-hold-frac', 'FACTOR', 'F4-MOM12-N20-TREND',
   'Same method as the whole-share F4: P7a dev window only; failed max DD <= 15% (22.2%). Backtested in whole shares; this version trades fractional shares',
   true, NULL),
  ('F1-SPY-SMA200-M-FR', 'F1 · Trend', 'SPY above its 200-day average, monthly, fractional shares',
   'shield', false, false, 8, 'book', 'monthly-hold-frac', 'TIMING', 'F1-SPY-SMA200-M',
   'Same method as the whole-share F1: P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11). Backtested in whole shares; this version trades fractional shares',
   true, NULL),
  ('RM-FR', 'RM · Braked momentum', 'Top 20 by rise beyond the market, holds less when jumpy, monthly, fractional shares',
   'activity', false, false, 9, 'book', 'monthly-hold-frac', 'RESIDVOL', NULL,
   'Lab M0011 dev window only (1996-01-03..2015-10-16), in whole shares: beats SPY TR (+660.2% vs +351.4%), max DD 14.1%, PF 2.03 and 1,588 trades all pass; failed only DSR >= 0.95 (0.897 at N=90). On paper to test it forward',
   true, 'M0011')
ON CONFLICT (id) DO NOTHING;

UPDATE strategies SET status = 'retired'
WHERE id IN ('F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M', 'FND') AND status = 'active';
