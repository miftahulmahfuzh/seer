-- Seer schema v2: engine bookkeeping. Written by engine/ (Python); web/ does not read these.
-- Additive only: three new tables and one partial unique index on runs.

-- Point-in-time index membership, one row per uninterrupted membership interval.
-- A symbol is a member of index_id on date D when start_date <= D AND (end_date IS NULL OR end_date > D).
CREATE TABLE IF NOT EXISTS universe (
  symbol         text NOT NULL,                 -- canonical dot form, same string as bars.symbol ('BRK.B')
  index_id       text NOT NULL CHECK (index_id IN ('SP500', 'NDX')),
  start_date     date NOT NULL,                 -- first day as a member (inclusive)
  end_date       date,                          -- first day no longer a member (EXCLUSIVE); NULL = still a member
  source_symbol  text NOT NULL,                 -- ticker(s) as written in the source dataset (before aliasing); when one
                                                -- interval spans a rename: every source ticker, oldest first, '/'-joined ('FB/META')
  PRIMARY KEY (index_id, symbol, start_date),
  CHECK (end_date IS NULL OR end_date > start_date)
);
CREATE INDEX IF NOT EXISTS universe_symbol_idx ON universe (symbol);

-- Splits seen by the nightly job. applied = history in bars was re-adjusted for this split.
-- Pre-split price / (split_to / split_from); pre-split volume * (split_to / split_from).
CREATE TABLE IF NOT EXISTS split_adjustments (
  symbol          text NOT NULL,
  execution_date  date NOT NULL,
  split_from      numeric NOT NULL CHECK (split_from > 0),
  split_to        numeric NOT NULL CHECK (split_to > 0),
  applied         boolean NOT NULL,
  recorded_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, execution_date)
);

-- One row per symbol the history backfill attempted; lets the backfill resume and
-- records which ever-members could not be fetched.
CREATE TABLE IF NOT EXISTS backfill_log (
  symbol      text PRIMARY KEY,
  status      text NOT NULL CHECK (status IN ('ok', 'empty', 'failed')),
  first_date  date,
  last_date   date,
  rows        int,
  error       text,
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- At most one real (non-demo) run per target session: a re-run reuses the row.
CREATE UNIQUE INDEX IF NOT EXISTS runs_real_session_uidx ON runs (session_date) WHERE NOT is_demo;
