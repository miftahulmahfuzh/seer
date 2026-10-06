-- Seer schema v8: every book strategy says what it would buy, every night.
-- Additive only: one nullable column and one new table. No row is touched.
--
-- paper_state.kickoff_session: the one session a book strategy ranked on OFF its cadence, its
-- first decision (paper.book.needs_kickoff). A monthly strategy whose clock starts mid-month
-- would otherwise sit in cash until the next month's first session. NULL = no kickoff (yet, or
-- never needed). paper_check replays it with run_book(kickoff=...).
--
-- book_previews: what a book strategy WOULD pick if it ranked tonight, written every night next
-- to the real decision. Display only: nothing trades on it and the replay never reads it. One
-- set per strategy (the newest night replaces the last).
ALTER TABLE paper_state ADD COLUMN IF NOT EXISTS kickoff_session date;

CREATE TABLE IF NOT EXISTS book_previews (
  strategy_id   text NOT NULL REFERENCES strategies(id),
  data_date     date NOT NULL,                  -- the bars the preview read (the night's session)
  rank          int NOT NULL CHECK (rank >= 1),
  symbol        text NOT NULL,
  weight        numeric(8,6) NOT NULL,
  last          numeric(12,4) NOT NULL,         -- the close on data_date
  PRIMARY KEY (strategy_id, rank)
);
