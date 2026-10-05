-- Seer schema v6: the roster becomes data (plan roster-promotion-pipeline, phase 1; R2, D2, D3).
-- Additive only, matching 003_paper.sql's discipline: nullable or defaulted columns on
-- `strategies`, no column dropped, no CHECK narrowed, migrations 001-005 untouched.
-- Written by engine/ (Python); web/ reads `status` and `paper_end` from the leaderboard.
--
-- Until now `paper/roster.py` held a compiled-in tuple and the `strategies` row held only the
-- display fields. These columns move the rest of a roster row into the database, so adding,
-- replacing or retiring a horseman is a row, not a code edit. The one thing a row cannot hold
-- is the live Python object, so it holds the object's STABLE NAME instead and
-- `paper.roster.RESOLVER` maps that name to the object (Decisions D2). A name the resolver does
-- not know is a hard error when the roster is built, never a silently dropped portfolio
-- (invariant 9) -- an `eval`-ed import path would have made this column a code-execution surface.
--
-- Lifecycle (D3, invariants 3 and 4): a horseman is replaced by INSERTING a new row and setting
-- the old row's status to 'retired', in one transaction. Retirement NEVER deletes
-- equity_snapshots, orders, book_* or paper_state rows, and never clears paper_start;
-- `paper_end` records the last session actually traded, so the leaderboard keeps the whole
-- track record and can say the row is retired rather than hiding it.

-- Lifecycle.
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active'
  CHECK (status IN ('active', 'retired'));      -- 'retired': keeps its history, stops trading
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS paper_end date;        -- last session traded; NULL while active
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS promoted_from text;    -- lab methods.id this row came from

-- The roster row's definition, read by paper.roster.from_row.
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS object_name text;      -- a paper.roster.RESOLVER key
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS registry_id text;      -- backtest.registry id (book entries), else NULL
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS gate_note text;        -- the display fact the go-live checklist reads
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS gate_applicable boolean NOT NULL DEFAULT true;

-- The five rows 003 and 004 inserted, given the definition fields they were missing. Every value
-- here is byte-for-byte paper/roster.py's SEED_ROWS; tests/test_paper_roster.py checks that
-- equality against a migrated database, and the spec digests pinned there must not move.
UPDATE strategies SET
  object_name = v.object_name,
  registry_id = v.registry_id,
  gate_note = v.gate_note,
  gate_applicable = v.gate_applicable
FROM (VALUES
  ('SPY', 'buy_and_hold', NULL,
   'Benchmark, not a strategy: it has no backtest gate and is never a Seer pick', true),
  ('A', 'STRATEGY_A', NULL,
   'P3 gate failed out of sample (2022-01-03..2026-10-02): -15.0% vs SPY TR +71.9%, PF 0.92, max DD 33.3%', true),
  ('F4-MOM12-N20-TREND', 'FACTOR', 'F4-MOM12-N20-TREND',
   'P7a dev window only; failed max DD <= 15% (22.2%)', true),
  ('F1-SPY-SMA200-M', 'TIMING', 'F1-SPY-SMA200-M',
   'P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11)', true),
  ('C', 'STRATEGY_C', NULL,
   'Backtest gate: not applicable (LLM strategy, design §1 item 5)', false)
) AS v(id, object_name, registry_id, gate_note, gate_applicable)
WHERE strategies.id = v.id;
