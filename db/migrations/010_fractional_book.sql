-- Seer schema v10: F4, F1 and FND trade fractional shares (owner, 2026-10-07).
--
-- Gotrade takes fractional LIMIT buys and sells (only its take-profit/stop-loss order needs whole
-- shares, and these three methods never use one). In whole shares a 10,000,000 IDR book could not
-- hold most of F4's and FND's 20 targets (about $55 each) and F1 could hold one SPY share of its
-- $1,116, so the paper record would not have been the method the owner trades.
--
-- A changed rule set is a NEW roster id (paper runbook, "The roster"): three new rows under
-- monthly-hold-frac, and the three whole-share rows retired. Retiring keeps every row they wrote;
-- the next paper night stamps their paper_end. paper_start, the frozen spec and the paper clock of
-- the new rows are written by that night, as for every new entry. Rows below are byte for byte
-- paper/roster.py's SEED_ROWS (the migration-equality test).
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable) VALUES
  ('F4-MOM12-N20-TREND-FR', 'F4 · Momentum', 'Top 20 by last year''s rise, monthly, fractional shares',
   'trending-up', false, false, 7, 'book', 'monthly-hold-frac', 'FACTOR', 'F4-MOM12-N20-TREND',
   'Same method as the whole-share F4: P7a dev window only; failed max DD <= 15% (22.2%). Backtested in whole shares; this version trades fractional shares',
   true),
  ('F1-SPY-SMA200-M-FR', 'F1 · Trend', 'SPY above its 200-day average, monthly, fractional shares',
   'shield', false, false, 8, 'book', 'monthly-hold-frac', 'TIMING', 'F1-SPY-SMA200-M',
   'Same method as the whole-share F1: P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11). Backtested in whole shares; this version trades fractional shares',
   true),
  ('FND-FR', 'FND · Fundamentals', 'Top 20 by company filings, monthly, fractional shares',
   'book-open', false, false, 9, 'book', 'monthly-hold-frac', 'FUNDAMENTAL', NULL,
   'Same method as the whole-share FND: M0005 dev window only; failed beats SPY TR (+1.8% vs +351.4%), >= 100 trades (15) and DSR >= 0.95 (0.006). Backtested in whole shares; this version trades fractional shares',
   true)
ON CONFLICT (id) DO NOTHING;

UPDATE strategies SET status = 'retired'
WHERE id IN ('F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M', 'FND') AND status = 'active';
