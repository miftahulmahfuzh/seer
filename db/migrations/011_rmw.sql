-- Seer schema v11: RMW (RM's book with its volatility brake read every week) replaces RM-FR
-- (owner, 2026-10-07).
--
-- Lab M0022's W-TV16 variant: the residual-momentum top 20, picked once a month, with the
-- one-month volatility brake re-read every week at a 16% swing limit, in fractional shares
-- (monthly-rank-weekly-resize-frac; paper runs split-cadence rules since the paper-split-cadence
-- set, merge 97374a8). It passes every owner rule on the dev window and fails only the luck test
-- (DSR 0.916 < 0.95, the lab's best). RM-FR never traded: paper was paused before its first
-- session, so retiring it hides it from the app (web/lib/data.ts strategies()).
-- RMW-FR is the row `promote --method M0022 --candidate M0022-W-TV16 --fractional --retire RM-FR
-- --lab-status-stays` writes on the live database; this file writes it everywhere else, byte for
-- byte paper/roster.py's SEED_ROWS (the migration-equality test).
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('RMW-FR', 'RM · Braked momentum',
   'Top 20 by rise beyond the market, picked monthly; holds less when jumpy, checked weekly; fractional shares',
   'activity', false, false, 10, 'book', 'monthly-rank-weekly-resize-frac', 'WEEKLYBRAKE', NULL,
   'Lab M0022 dev window only (1996-01-03..2015-10-16), in whole shares: beats SPY TR (+789.2% vs +351.4%), max DD 14.3%, PF 2.06 and 1,589 trades all pass; failed only DSR >= 0.95 (0.916 at N=110). On paper to test it forward',
   true, 'M0022')
ON CONFLICT (id) DO NOTHING;

UPDATE strategies SET status = 'retired' WHERE id = 'RM-FR' AND status = 'active';
