-- Seer schema v12: which Journal entries the reader has already seen (/sera/journal badges).
--
-- The seven badges on /sera/journal counted how many entries of each kind EXIST -- a number that
-- only ever grows, because the lab is append-only. They now count how many are NEW to the reader,
-- which needs somewhere to remember what has already been looked at.
--
-- insight_id is `insights.id` from the engine's SQLite lab store
-- (engine/src/seer_engine/lab/store.py), carried verbatim into web/data/lab.json. That table is
-- append-only by construction: the insights_no_update and insights_no_delete triggers RAISE(ABORT)
-- on any UPDATE or DELETE, so an id, once issued, names the same insight forever and is never
-- reused. There is therefore NO foreign key here -- the insights themselves do not live in
-- Postgres, and there is nothing to cascade from. An id with no matching insight (a snapshot
-- rolled back by hand, say) is simply ignored by the reader.
--
-- No user column, for the same reason action_dismissals (001_init.sql) has none: Seer is private
-- to one Google account (web/lib/allow.ts) and /sera to one narrower still (web/lib/sera/access.ts).
--
-- via records HOW the entry was marked: 'click' when the reader opened the method behind the
-- card's redirect arrow, 'view' when the card simply dwelled on screen in a visible tab.
-- Diagnostics only -- nothing reads it to decide seen-ness. A row existing is what "seen" means.
--
-- Rows are only ever inserted, never updated or deleted: the first marking wins and a repeat is an
-- ON CONFLICT DO NOTHING no-op (web/lib/sera/seen.ts markInsightsSeen). Nothing in this plan set
-- marks an entry unseen.
CREATE TABLE IF NOT EXISTS journal_seen (
  insight_id  bigint PRIMARY KEY,
  seen_at     timestamptz NOT NULL DEFAULT now(),
  via         text NOT NULL DEFAULT 'view' CHECK (via IN ('view', 'click'))
);
