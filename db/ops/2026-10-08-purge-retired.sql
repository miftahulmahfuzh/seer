-- A one-off production operation, run 2026-10-08: delete every retired strategy and the rows it
-- wrote. APPLIED TO PRODUCTION; not replayed anywhere else.
--
-- WHY THIS IS NOT A MIGRATION, which is the thing to understand before writing another one.
--
-- `db/migrations/` is a replay of history: 003, 004, 007, 010, 011 and 013 each INSERT the roster
-- entries that existed when they ran, and `engine/tests/conftest.py`'s `pg` fixture builds every
-- database test's world by applying all of them to a throwaway schema. So the migration set is not
-- only "the schema" -- it is the fixture 146 tests are written against, by id: 40 uses of `A`, 27
-- of `SPY`, 18 of `C`.
--
-- Shipping this as `018_purge_retired.sql` therefore deleted those entries out from under the test
-- suite, and the run went from 3482 passed to 146 failed with ForeignKeyViolation on
-- `news_vetoes.strategy_id = 'C'`. The failure was correct: a migration that deletes seed data
-- rewrites the replay. Production wants these rows gone; the replay needs them to have existed.
-- Those are different statements, and only the first is an operation.
--
-- Run it by hand against production, never from `seer migrate`:
--     psql "$DATABASE_URL_UNPOOLED" -f db/ops/2026-10-08-purge-retired.sql
--
-- The lock that does NOT depend on this having run is `web/lib/data.ts`, which filters
-- `status <> 'retired'`: a rebuilt database may carry the historical rows again, and the app still
-- will not show them.
--
-- WHY THE DELETE WAS SAFE, and why it would NOT have been a week later.
--
-- Paper was paused (nightly.yml, PAPER_PAUSED) with the clock frozen at ZERO stepped sessions, so
-- not one retired entry ever traded. Six of the thirteen carry a `paper_start` of 2026-10-07 and
-- look like they have a record; they do not. What they hold is the day-0 snapshot written at start
-- (one equity_snapshots row each, equity unchanged from the initial capital), the paper_state row
-- beside it, and the first-night decisions that were never executed -- 80 book_targets, 80
-- book_previews, 4 orders and 20 news_vetoes, all dated 2026-10-07 and all still pending.
--
-- That single unchanged equity point is what made the leaderboard render "+0.0% Total return" on
-- 0 trades for six cards: a number computed from a start value and nothing else, which reads as a
-- result and is actually "never ran". Deleting these rows removes no measurement, because no
-- measurement was ever taken. Owner's call, 2026-10-08: "it is fine to purge them because it is
-- just a first day recommendation".
--
-- The other seven (A, FND, RM-FR, and the whole-share F1/F4 pairs) were retired by 013 and 017
-- before their first session and have no rows at all.
--
-- `paper/roster.py` keeps all thirteen in SEED_ROWS with `status="retired"`, which is the lineage
-- record and is deliberately NOT touched here: `roster.active()` filters on `status == "active"`,
-- so the nightly can never re-start one and these rows can never come back on their own.
--
-- Reversible from `.workflows/orchestration/gotrade-fee-rebuild/logs/pre-018-retired-purge.json`,
-- which holds all 209 rows as they stood before this ran.
--
-- Children first: every foreign key into `strategies` is ON DELETE NO ACTION.

DELETE FROM book_fills        WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');
DELETE FROM book_trades       WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');
DELETE FROM book_positions    WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');
DELETE FROM book_previews     WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');
DELETE FROM book_targets      WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');
DELETE FROM orders            WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');
DELETE FROM news_vetoes       WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');
DELETE FROM equity_snapshots  WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');
DELETE FROM paper_contributions WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');
DELETE FROM paper_state       WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');
DELETE FROM sean_link         WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');
DELETE FROM sean_reminder_marks WHERE strategy_id IN (SELECT id FROM strategies WHERE status = 'retired');

DELETE FROM strategies WHERE status = 'retired';
