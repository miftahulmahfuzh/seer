-- Seer schema v7: FND, point-in-time SEC fundamental factors, joins the paper roster
-- (plan roster-promotion-pipeline, phase 6; requirement R1).
-- Additive only: one roster display row, in 004_news_veto.sql's shape. No column is added,
-- dropped or narrowed, and no existing row is touched.
--
-- WHY A MIGRATION WHEN PHASE 5's `promote` WRITES THIS ROW. The two write the same row for two
-- different databases. `promote --method M0005 --id FND` writes it to the live Neon instance,
-- which is already migrated and whose roster is data (006_roster.sql). This file writes it to
-- every database that is brought up from migrations instead -- CI's throwaway schema, a fresh
-- local train database, a rebuilt Neon -- so that `paper` finds a strategies row for every
-- roster entry (commands/paper.py plan_night) and the roster/migration equality test holds.
--
-- THE FROZEN SPEC, paper_start AND THE PAPER CLOCK ARE NOT WRITTEN HERE. `paper` writes them on
-- the first night (store.freeze_spec), exactly as it does for SPY, A, F4, F1 and C. A row with
-- no paper_start is a strategy that starts on the next night; that is phase 2's path and FND is
-- its first user.
--
-- THE DEFINITION COLUMNS ARE NOT OPTIONAL. 006_roster.sql moved object_name, registry_id,
-- gate_note and gate_applicable onto `strategies`, and paper/roster.py's `from_row` READS them:
-- a row with a NULL object_name raises UnknownObject and one with no gate_note raises
-- BadRosterRow, either of which stops the whole paper night (invariant 9). They are also what
-- test_paper_roster.py's migration-equality test compares against SEED_ROWS. So every value below
-- is byte-for-byte roster.py's FND seed row.
--
-- status IS DELIBERATELY NOT NAMED. 006_roster.sql gives it DEFAULT 'active', which is what FND
-- wants, so leaving it out stops the ON CONFLICT branch from resurrecting a strategy someone has
-- since retired. (This file does require 006: it names 006's columns.)
--
-- promoted_from IS WRITTEN ON INSERT AND NEVER ON UPDATE. 'M0005' is the honest provenance: FND's
-- allocator and parameters are lab method M0005's M0005-ALL candidate, taken off that Candidate
-- unchanged, and `promote --method M0005 --candidate M0005-ALL` records exactly that on the live
-- database. It asserts no lab STATUS transition -- M0005 stays 'rejected', because the lab's
-- `transitions` table has no row whose src is 'rejected' and promote's --lab-status-stays is the
-- acknowledgement of that. Keeping it out of the DO UPDATE list means re-running this file can
-- never clobber what promote wrote.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('FND', 'FND · Fundamentals', 'Top 20 by SEC filing factors, monthly', 'book-open', false, false,
   6, 'book', 'monthly-hold',
   'FUNDAMENTAL', NULL,
   'M0005 dev window only (1996-01-03..2015-10-16, fundamental coverage 0.3151); failed beats SPY TR (+1.8% vs +351.4%), >= 100 trades (15) and DSR >= 0.95 (0.006)',
   true, 'M0005')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, sub = EXCLUDED.sub, icon = EXCLUDED.icon,
  is_champion = EXCLUDED.is_champion, is_benchmark = EXCLUDED.is_benchmark, sort = EXCLUDED.sort,
  engine = EXCLUDED.engine, rules_id = EXCLUDED.rules_id, object_name = EXCLUDED.object_name,
  registry_id = EXCLUDED.registry_id, gate_note = EXCLUDED.gate_note,
  gate_applicable = EXCLUDED.gate_applicable;
